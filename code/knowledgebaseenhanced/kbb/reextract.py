"""Targeted re-extraction of documents the audit flagged (one document at a time).

Why this exists: ``scripts/build_markdown_corpus.py`` lost the body of several HTML pages and could not
read image-only PDFs, so heading-only Markdown reached the index.  This module re-reads *only the flagged
documents* with the pipeline's own readers:

* HTML  -> ``kbb.extract.html_reader`` (BeautifulSoup) with site-wide navigation removed by frequency
* scanned PDF -> page renders + Tesseract (``eng+hin`` from the pinned tessdata) – status ``needs_review``
  until a reviewer compares the text with the page image (see ``kbb.reviews``)

Nothing here lets a model write evidence text.  Text is verbatim reader output, whitespace-cleaned.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from .audit import _DEV_TOKEN, split_frontmatter
from .config import Config
from .models import Table
from .textnorm import clean

FRONT_KEYS = ("doc_id", "title", "category", "source_file", "source_sha256", "reader", "status", "tags")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def grid_to_markdown(grid: list[list[str]]) -> str:
    """Pipe table with the first row as header; cells keep their verbatim text."""
    if not grid or not grid[0]:
        return ""
    width = max(len(r) for r in grid)
    rows = [[(c or "").replace("|", "/").replace("\n", " ").strip() for c in r] + [""] * (width - len(r)) for r in grid]
    out = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join("---" for _ in range(width)) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def chrome_lines(html_files: list[Path], cfg: Config, min_share: float = 0.35) -> set[str]:
    """Lines present on a large share of pages are site navigation, not content."""
    from .extract import html_reader
    counts: Counter = Counter()
    n = 0
    for path in html_files:
        try:
            lines = {clean(e.text) for e in html_reader.read_html(cfg, str(path), prune_nav=True) if e.type != "table"}
        except Exception:
            continue
        n += 1
        counts.update(l for l in lines if l)
    return {line for line, c in counts.items() if n >= 4 and c / n >= min_share}


def html_to_markdown(cfg: Config, path: Path, chrome: set[str] | None = None) -> tuple[str, int]:
    """Verbatim body Markdown of an HTML page.  Returns (markdown, dropped_navigation_lines)."""
    from .extract import html_reader
    chrome = chrome or set()
    parts: list[str] = []
    dropped = 0
    for el in html_reader.read_html(cfg, str(path), prune_nav=True):
        text = clean(el.text)
        if not text:
            continue
        if el.type != "table" and text in chrome:
            dropped += 1
            continue
        if el.type == "heading":
            parts.append("#" * min(6, max(2, el.level or 2)) + " " + text)
        elif el.type == "list_item":
            parts.append("- " + text)
        elif el.type == "table" and el.table:
            parts.append(grid_to_markdown(el.table.grid()))
        else:
            parts.append(text)
    return "\n\n".join(parts), dropped


def footer_contact_lines(path: Path) -> list[str]:
    """Address/helpline lines that Drupal pages keep only in the footer (verbatim)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(path.read_bytes().decode("utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    lines = [clean(t) for t in soup.get_text("\n").splitlines()]
    keep = [l for l in lines if re.search(r"(?i)helpline|plot no\.? ?7|goo\.gl/maps|railway station|airport", l)]
    return list(dict.fromkeys(keep))


def drop_garbled_lines(text: str) -> tuple[str, list[str]]:
    """Remove lines whose Devanagari glyphs were damaged by a font-less PDF text layer.

    Damaged lines cannot be repaired without guessing, so they are *removed and reported* – never rewritten.
    """
    kept, removed = [], []
    for line in text.splitlines():
        tokens = _DEV_TOKEN.findall(line)
        bad = sum(1 for t in tokens if t[0] in "\u093e\u093f\u0940\u0941\u0942\u0943\u0947\u0948\u094b\u094c\u094d\u0901\u0902\u0903" or t.endswith("\u094d"))
        gaps = len(re.findall(r"[\u0900-\u097f] {2,}[\u0900-\u097f]", line))
        if tokens and (bad + gaps) / len(tokens) >= 0.12 and (bad + gaps) >= 1:
            removed.append(line.strip())
        else:
            kept.append(line)
    return "\n".join(kept), removed


def ocr_pdf_pages(cfg: Config, pdf: Path, sha256: str, dpi: int | None = None) -> list[tuple[int, str]]:
    """Render every page and OCR it with Tesseract (eng+hin)."""
    import pypdfium2 as pdfium
    from .extract import tesseract_reader
    from .render import render_pages
    n_pages = len(pdfium.PdfDocument(str(pdf)))
    dpi = dpi or cfg.triage.ocr_dpi
    images = render_pages(cfg, str(pdf), sha256, list(range(1, n_pages + 1)), dpi)
    out = []
    for page in range(1, n_pages + 1):
        text, _ = tesseract_reader.ocr_words(cfg, str(images[page]), scale=72.0 / dpi)
        out.append((page, clean(text)))
    return out


def compose_document(meta: dict, title: str, pages: list[tuple[int, str]] | None = None, body: str | None = None) -> str:
    """Front matter + page-anchored body, in the format ``kbb.mdcorpus`` parses."""
    lines = ["---"]
    for key in FRONT_KEYS:
        value = meta.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, list):
            lines.append(f"{key}: [" + ", ".join(f'"{v}"' for v in value) + "]")
        else:
            lines.append(f'{key}: "{str(value).replace(chr(34), chr(39))}"')
    lines += ["---", "", f"# {title}", ""]
    if pages is not None:
        for page, text in pages:
            lines += [f"<!-- page: {page} -->", "", text, ""]
    else:
        lines += [body or "", ""]
    return "\n".join(lines).rstrip() + "\n"


def reextract_document(cfg: Config, processed_dir: Path, source_root: Path, doc_id: str,
                       chrome: set[str] | None = None) -> dict:
    """Re-read one flagged document from its original source and rewrite its Markdown.

    Returns a small report (reader, status, words).  The previous Markdown is kept next to it as
    ``<name>.md.prev`` so the change is reversible.
    """
    md_path = next((p for p in processed_dir.rglob("*.md") if split_frontmatter(p.read_text(encoding="utf-8"))[0].get("doc_id") == doc_id), None)
    if md_path is None:
        raise FileNotFoundError(doc_id)
    text = md_path.read_text(encoding="utf-8")
    meta, _ = split_frontmatter(text)
    source = source_root / meta["source_file"]
    if not source.exists():
        raise FileNotFoundError(source)
    meta["source_sha256"] = file_sha256(source)
    title = meta.get("title", doc_id)
    suffix = source.suffix.lower()
    removed: list[str] = []
    if suffix in {".html", ".htm"}:
        body, dropped = html_to_markdown(cfg, source, chrome)
        if len(body.split()) < 20:
            footer = footer_contact_lines(source)
            if footer:
                body = (body + "\n\n## Contact details (page footer)\n\n" + "\n\n".join(footer)).strip()
        meta.update(reader="kbb-html", status="extracted")
        new = compose_document(meta, title, body=body)
        removed = [f"{dropped} navigation lines"]
    elif suffix == ".pdf":
        pages = ocr_pdf_pages(cfg, source, meta["source_sha256"])
        cleaned = []
        for page, page_text in pages:
            kept, bad = drop_garbled_lines(page_text)
            removed += bad
            cleaned.append((page, kept))
        meta.update(reader="tesseract-eng+hin", status="needs_review")
        new = compose_document(meta, title, pages=cleaned)
    else:
        raise ValueError(f"unsupported source type {suffix}")
    (md_path.with_suffix(".md.prev")).write_text(text, encoding="utf-8")
    md_path.write_text(new, encoding="utf-8")
    return {"doc_id": doc_id, "path": str(md_path), "reader": meta["reader"], "status": meta["status"],
            "words": len(new.split()), "removed": removed[:20]}
