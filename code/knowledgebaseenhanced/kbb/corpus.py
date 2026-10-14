"""Load the Markdown corpus into canonical elements with *honest* verification statuses.

Statuses (see ``kbb.models``): ``approved`` > ``extracted`` > ``machine_verified`` > ``needs_review``.

* ``extracted``        - born-digital text (HTML, PDF text layer, plain text); structure checks only
* ``approved``         - a recorded visual review of the page (``kbb.reviews``) or imported reviewed evidence
* ``machine_verified`` - reserved for OCR pages whose independent second read agreed; this loader never
                         invents it (no second read is available in this environment)
* ``needs_review``     - OCR/scan/image-derived text nobody has compared with the page: stored, never served
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .audit import split_frontmatter
from .models import Element
from .reextract import drop_garbled_lines, file_sha256
from .tables import from_markdown, render_rows
from .textnorm import clean

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
PAGE_ANCHOR = re.compile(r"^<!--\s*page:\s*(\d+)\s*-->$")
YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


@dataclass
class DocRecord:
    meta: dict
    elements: list[Element] = field(default_factory=list)
    page_status: dict[int, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)       # audit trail: dropped lines, applied reviews


def split_pages(body: str) -> list[tuple[int, str]]:
    """Body split on ``<!-- page: N -->`` anchors.  Pageless documents return one page ``-1``."""
    pages: list[tuple[int, list[str]]] = []
    current: tuple[int, list[str]] = (-1, [])
    for line in body.splitlines():
        match = PAGE_ANCHOR.match(line.strip())
        if match:
            if current[1] or current[0] != -1:
                pages.append(current)
            current = (int(match.group(1)), [])
        else:
            current[1].append(line)
    pages.append(current)
    return [(p, "\n".join(lines).strip("\n")) for p, lines in pages if "\n".join(lines).strip() or p != -1]


def parse_page(doc_id: str, page: int, text: str, start_index: int, status: str, reader: str) -> list[Element]:
    """Headings, list items, tables and paragraphs of one page, text verbatim (whitespace-cleaned)."""
    elements: list[Element] = []
    para: list[str] = []
    table: list[str] = []
    idx = start_index

    def add(kind, body, **kw):
        nonlocal idx
        elements.append(Element(id=f"{doc_id}:e{idx:04d}", type=kind, page=page, text=body, reader=reader,
                                status=status, order=idx, **kw))
        idx += 1

    def flush_para():
        if para:
            body = clean("\n".join(para))
            if body:
                add("paragraph", body)
            para.clear()

    def flush_table():
        if table:
            t = from_markdown("\n".join(table))
            if t and t.n_rows > 0:
                add("table", render_rows(t), table=t)
            table.clear()

    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            flush_para()
            table.append(line)
            continue
        flush_table()
        heading = re.match(r"^(#{1,6})\s+(.*)$", s)
        item = re.match(r"^(?:[-*+]|\d+\.)\s+(.*)$", s)
        if heading:
            flush_para()
            body = clean(heading.group(2))
            if body:
                add("heading", body, level=len(heading.group(1)))
        elif item:
            flush_para()
            body = clean(item.group(1))
            if body:
                add("list_item", body)
        elif not s:
            flush_para()
        else:
            para.append(line)
    flush_para()
    flush_table()
    return elements


def pdf_native_pages(pdf: Path, min_chars: int = 40) -> tuple[set[int], int]:
    """(pages with a real text layer, total pages).  Pages without one were OCR'd, so they cannot be 'extracted'."""
    import pypdfium2 as pdfium
    native = set()
    document = pdfium.PdfDocument(str(pdf))
    for index in range(len(document)):
        if document[index].get_textpage().count_chars() >= min_chars:
            native.add(index + 1)
    return native, len(document)


def resolve_sources(source_root: Path, source_file: str) -> list[Path]:
    """Files behind ``source_file``; merged documents name a glob such as ``general/Slide[3-26].jpg``."""
    direct = source_root / source_file
    if direct.exists():
        return [direct]
    pattern = re.sub(r"\[[^\]]*\]", "*", Path(source_file).name).split(" (")[0].split(" & ")[0]
    parent = (source_root / source_file).parent
    return sorted(parent.glob(pattern)) if parent.exists() else []


def source_digest(files: list[Path]) -> str:
    """Real digest for single files and merged documents (the old 'multi-slide-synthesis' was a placeholder)."""
    if len(files) == 1:
        return file_sha256(files[0])
    import hashlib
    h = hashlib.sha256()
    for path in files:
        h.update(file_sha256(path).encode())
    return h.hexdigest()


def doc_years(meta: dict) -> list[int]:
    years = {int(y) for y in YEAR.findall(" ".join([meta.get("title", ""), meta.get("source_file", "")]))}
    for start, end in re.findall(r"(20\d{2})[_-](\d{2})(?!\d)", meta.get("source_file", "")):
        years.update(range(int(start), int(start[:2] + end) + 1))
    return sorted(years)


def base_page_status(meta: dict, page: int, source_files: list[Path], native: dict[Path, tuple[set[int], int]]) -> str:
    """Status before any review.  Images, scans and OCR output start as ``needs_review``."""
    if meta.get("reader", "").startswith("tesseract") or meta.get("status") == "needs_review":
        return "needs_review"
    if not source_files or any(f.suffix.lower() in IMAGE_EXT for f in source_files):
        return "needs_review"
    if source_files[0].suffix.lower() == ".pdf":
        if source_files[0] not in native:
            native[source_files[0]] = pdf_native_pages(source_files[0])
        pages, total = native[source_files[0]]
        if page == -1:                       # no page anchors: judge the document by its text-layer coverage
            return "extracted" if len(pages) >= 0.5 * max(total, 1) else "needs_review"
        return "extracted" if page in pages else "needs_review"
    return "extracted"


def load_document(path: Path, source_root: Path, native: dict[Path, tuple[set[int], int]], page_reviews=None,
                  overrides: dict | None = None) -> DocRecord:
    """Parse one Markdown file; apply recorded page reviews and reviewed-evidence overrides."""
    from .reviews import apply_page_review
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = split_frontmatter(text)
    meta.setdefault("doc_id", path.stem)
    files = resolve_sources(source_root, meta.get("source_file", ""))
    if files:
        meta["source_sha256"] = source_digest(files)
    meta["years"] = doc_years(meta)
    meta["historical"] = bool(meta["years"]) and max(meta["years"]) <= 2024
    record = DocRecord(meta=meta)
    idx = 1
    for page, page_text in split_pages(body):
        status = base_page_status(meta, page, files, native)
        if page == -1 and files and files[0].suffix.lower() == ".pdf" and all(
                ln.strip().startswith("#") or not ln.strip() for ln in page_text.splitlines()) and len(record.page_status) == 0 and idx == 1:
            status = "extracted"            # the title line before the first page anchor carries no OCR risk
        reader = meta.get("reader") or ("html" if files and files[0].suffix.lower() in {".html", ".htm"} else "native-text")
        override = (overrides or {}).get(page)
        if override:                       # reviewed evidence imported from the previous release
            page_text, status, reader = override["text"], override["status"], override["reader"]
            record.notes.append(f"page {page}: reviewed text imported ({override['reviewer']})")
        page_text, dropped = drop_garbled_lines(page_text)
        if dropped:
            record.notes.append(f"page {page}: dropped {len(dropped)} line(s) with damaged Devanagari glyphs")
        review = page_reviews(meta["doc_id"], page, meta.get("source_sha256", "")) if page_reviews else None
        if review:
            page_text, status = apply_page_review(page_text, review)
            record.notes.append(f"page {page}: {review['decision']} by {review['reviewer']}")
        record.page_status[page] = status
        if status == "rejected" or not page_text.strip():
            continue
        els = parse_page(meta["doc_id"], page, page_text, idx, status, reader)
        idx += len(els)
        record.elements.extend(els)
    return record


def load_corpus(processed_dir: Path, source_root: Path, page_reviews=None, overrides_by_source=None,
                only: set[str] | None = None) -> list[DocRecord]:
    native: dict[Path, set[int]] = {}
    docs = []
    for path in sorted(processed_dir.rglob("*.md")):
        if path.name == "SUMMARY.md":
            continue
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if only and meta.get("doc_id") not in only:
            continue
        override = (overrides_by_source or {}).get(Path(meta.get("source_file", "")).name)
        docs.append(load_document(path, source_root, native, page_reviews, override))
    return docs
