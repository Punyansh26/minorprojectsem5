"""Extract inspectable text, tables and visual evidence without promoting uncertain OCR."""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pdfplumber
from PIL import Image

from assistant.config import settings
from assistant.kb.common import PIPELINE_VERSION, digest, now, read_json, write_json
from assistant.kb.sources import html_main


def clean(text: str) -> str:
    """Normalize whitespace without silently correcting numbers or OCR spelling."""
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip())


def table_text(rows: list[list[str | None]]) -> str:
    """Retain all columns, blank cells and merged-header context for verification."""
    return "\n".join(" | ".join(clean(str(cell)) if cell is not None else "" for cell in row) for row in rows)


def ocr_image(image: Image.Image, state: Path) -> tuple[str, list[dict]]:
    """Return words with coordinates/confidence; OCR output always starts unverified."""
    tessdata = state / "models/tessdata"
    args = ["tesseract", "stdin", "stdout", "--psm", "6"]
    if (tessdata / "hin.traineddata").exists():
        for name in ("eng", "osd"):
            target = tessdata / f"{name}.traineddata"
            if not target.exists() and Path(f"/usr/share/tessdata/{name}.traineddata").exists():
                shutil.copyfile(f"/usr/share/tessdata/{name}.traineddata", target)
        args.extend(["--tessdata-dir", str(tessdata), "-l", "eng+hin"])
    else:
        args.extend(["-l", "eng"])
    # An explicit parameter works with a workspace tessdata directory without configs/.
    args.extend(["-c", "tessedit_create_tsv=1"])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    result = subprocess.run(args, input=buffer.getvalue(), capture_output=True, timeout=120, check=True)
    words, lines = [], {}
    for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8", errors="replace")), delimiter="\t", quoting=csv.QUOTE_NONE):
        if not row.get("text", "").strip() or row.get("level") != "5":
            continue
        word = {k: int(row[k]) for k in ("left", "top", "width", "height")}
        word.update(text=row["text"], confidence=float(row["conf"]))
        words.append(word)
        key = tuple(row[k] for k in ("block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(row["text"])
    return "\n".join(" ".join(line) for line in lines.values()), words


def scanned_grid(image: Image.Image, words: list[dict]) -> list[list[str]]:
    """Recover ruled table cells from line geometry; ambiguous results remain review-only."""
    import cv2
    import numpy as np
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    height, width = gray.shape
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 15), 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, height // 20))))

    def centers(values, threshold):
        indexes = np.flatnonzero(values > threshold)
        groups = []
        for index in indexes:
            if not groups or index - groups[-1][-1] > 4:
                groups.append([int(index)])
            else:
                groups[-1].append(int(index))
        return [sum(g) / len(g) for g in groups]

    xs = centers((vertical > 0).sum(axis=0), height * .10)
    ys = centers((horizontal > 0).sum(axis=1), width * .35)
    if len(xs) < 3 or len(ys) < 3:
        return []
    rows = []
    for y0, y1 in zip(ys, ys[1:]):
        cells = []
        for x0, x1 in zip(xs, xs[1:]):
            selected = [w for w in words if x0 < w["left"] + w["width"] / 2 < x1
                        and y0 < w["top"] + w["height"] / 2 < y1]
            cells.append(" ".join(w["text"] for w in selected))
        if any(cells):
            rows.append(cells)
    return rows


def make_block(source: dict, page: int, kind: str, text: str, **extra) -> dict:
    """Carry evidence provenance through chunking, indexing and answer citations."""
    text = clean(text)
    key = digest(json.dumps([source["sha256"], page, kind, text, extra.get("bbox", [])], ensure_ascii=False))[:24]
    block = {"id": key, "source_id": source["id"], "source_file": source.get("source_file", source["title"]),
             "source_url": source.get("final_url", source.get("url", "")), "title": source["title"],
             "category": source.get("category", "general"), "topic": source.get("topic", "general"),
             "page_number": page, "kind": kind, "text": text, "source_sha256": source["sha256"],
             "years": source.get("years", []), "period": source.get("period", ""),
             "programme": source.get("programme", ""), "published_at": source.get("published_at", ""),
             "fetched_at": source.get("fetched_at", ""), "historical": source.get("historical", False),
             "verification_status": "extracted", "extraction_method": "native", **extra}
    # Garbled Indic fonts and control characters must not become answer evidence.
    if "\x00" in text or "\ufffd" in text or "(cid:" in text:
        block["verification_status"] = "needs_review"
        block["review_reason"] = "Unreadable font/text encoding"
    return block


def extract_pdf(source: dict, state: Path, assets: Path) -> tuple[list[dict], list[dict]]:
    """Keep tables out of prose, OCR image regions, and account for every PDF page."""
    blocks, pages = [], []
    with pdfplumber.open(state / source["path"]) as pdf:
        # Repeated top/bottom lines are layout noise, not section content.
        edge_counts = Counter()
        for page in pdf.pages:
            lines = (page.extract_text() or "").splitlines()
            edge_counts.update(set(lines[:2] + lines[-2:]))
            page.close()
        repeated = {line for line, count in edge_counts.items() if count >= max(3, len(pdf.pages) * .6)}
        for page in pdf.pages:
            page_blocks = []
            try:
                text = page.extract_text() or ""
                legacy_font = any(re.search(r"kruti|chanakya|devlys", c.get("fontname", ""), re.I) for c in page.chars)
                legacy_font = legacy_font or bool(re.search(r"Nk=o|vk;qDr|fuEukuqlkj", text))
                if legacy_font or (len(re.sub(r"\W", "", text)) < 40 and page.images):
                    rendered = page.to_image(resolution=settings.KB_OCR_DPI).original
                    asset = assets / f"page-{page.page_number}.png"
                    rendered.save(asset)
                    text, words = ocr_image(rendered, state)
                    rows = scanned_grid(rendered, words)
                    page_blocks.append(make_block(source, page.page_number, "scanned_page", text,
                        extraction_method="tesseract", verification_status="needs_review", rows=rows,
                        asset=asset.relative_to(state).as_posix(), bbox=[0, 0, float(page.width), float(page.height)],
                        ocr_confidence=round(sum(w["confidence"] for w in words) / max(1, len(words)), 2),
                        review_reason="Verify OCR numbers, dates, table associations and reading order"))
                else:
                    tables = page.find_tables()
                    # Tiny layout boxes on brochures/web printouts are not semantic tables.
                    tables = [t for t in tables if len(t.rows) >= 2 and len(t.columns) >= 2
                              and t.bbox[0] >= page.bbox[0] and t.bbox[1] >= page.bbox[1]
                              and t.bbox[2] <= page.bbox[2] and t.bbox[3] <= page.bbox[3]]
                    if not tables and re.search(r"Fee Type|EVENT\s+DATE|Opening Rank|Academic Year", text, re.I):
                        tables = page.find_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
                    for index, table in enumerate(tables, 1):
                        rows = table.extract()
                        if not any(any(c for c in row) for row in rows):
                            continue
                        crop = page.crop(table.bbox).to_image(resolution=150).original
                        asset = assets / f"page-{page.page_number}-table-{index}.png"
                        crop.save(asset)
                        page_blocks.append(make_block(source, page.page_number, "table", table_text(rows),
                            rows=rows, bbox=list(map(float, table.bbox)), table_id=f"table-{index}",
                            asset=asset.relative_to(state).as_posix(), verification_status="needs_review",
                            review_reason="Verify column headers, merged cells, units, footnotes and row periods"))
                    def outside_tables(obj):
                        x = (obj.get("x0", 0) + obj.get("x1", 0)) / 2
                        y = (obj.get("top", 0) + obj.get("bottom", 0)) / 2
                        return not any(t.bbox[0] <= x <= t.bbox[2] and t.bbox[1] <= y <= t.bbox[3] for t in tables)
                    prose = page.filter(outside_tables).extract_text() or ""
                    prose = "\n".join(line for line in prose.splitlines() if line not in repeated)
                    if len(re.sub(r"[\W\d_]", "", prose)) >= 25:
                        page_blocks.append(make_block(source, page.page_number, "text", prose))
                    for index, info in enumerate(page.images, 1):
                        box = (max(page.bbox[0], info["x0"]), max(page.bbox[1], info["top"]), min(page.bbox[2], info["x1"]), min(page.bbox[3], info["bottom"]))
                        if box[2] - box[0] < 90 or box[3] - box[1] < 45:
                            continue
                        crop = page.crop(box).to_image(resolution=150).original
                        asset = assets / f"page-{page.page_number}-figure-{index}.png"
                        crop.save(asset)
                        visual_text, words = ocr_image(crop, state)
                        has_words = len(re.findall(r"\w{3,}", visual_text)) >= 4
                        page_blocks.append(make_block(source, page.page_number, "figure", visual_text,
                            bbox=list(map(float, box)), asset=asset.relative_to(state).as_posix(),
                            extraction_method="tesseract", verification_status="needs_review" if has_words else "visual_only",
                            review_reason="Check figure labels and caption; do not infer unlabeled values"))
                    # Vector plots do not necessarily appear in page.images.
                    if len(page.curves) > 15 and not page.images:
                        asset = assets / f"page-{page.page_number}-vector.png"
                        page.to_image(resolution=150).original.save(asset)
                        page_blocks.append(make_block(source, page.page_number, "vector_figure", "",
                            asset=asset.relative_to(state).as_posix(), verification_status="needs_review",
                            review_reason="Inspect vector illustration; native text alone may omit relationships"))
                status = "extracted" if any(b["verification_status"] == "extracted" for b in page_blocks) else "needs_review" if page_blocks else "blank"
                pages.append({"page": page.page_number, "status": status, "blocks": len(page_blocks)})
                blocks.extend(page_blocks)
            except Exception as error:
                blocks.extend(page_blocks)
                pages.append({"page": page.page_number, "status": "error", "error": type(error).__name__, "detail": str(error)[:200]})
            finally:
                page.close()
    return blocks, pages


def html_rows(table) -> list[list[str]]:
    """Expand explicit HTML row/column spans while retaining empty cells."""
    grid = {}
    trs = table.find_all("tr")
    for row, tr in enumerate(trs):
        col = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while (row, col) in grid:
                col += 1
            span_r = min(100, int(cell.get("rowspan", 1)))
            span_c = min(100, int(cell.get("colspan", 1)))
            for dr in range(span_r):
                for dc in range(span_c):
                    grid[row + dr, col + dc] = cell.get_text(" ", strip=True)
            col += span_c
    width = max((c for _, c in grid), default=-1) + 1
    return [[grid.get((r, c), "") for c in range(width)] for r in range(len(trs))]


def extract_source(source: dict, state: Path) -> dict:
    """Cache raw extraction independently of later manual corrections and approvals."""
    key = digest(source["sha256"] + PIPELINE_VERSION + str(settings.KB_OCR_DPI))
    cache = state / "extracted" / (source["id"] + "-" + key[:16] + ".json")
    cached = read_json(cache)
    if cached:
        return cached
    assets = state / "assets" / source["sha256"][:20]
    assets.mkdir(parents=True, exist_ok=True)
    path = state / source["path"]
    suffix = path.suffix.lower()
    blocks, pages = [], []
    if suffix == ".pdf":
        blocks, pages = extract_pdf(source, state, assets)
    elif suffix == ".html":
        soup, main = html_main(path.read_text(errors="replace"))
        for i, table in enumerate(main.find_all("table"), 1):
            rows = html_rows(table)
            heading = table.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
            caption = heading.get_text(" ", strip=True) if heading else source["title"]
            blocks.append(make_block(source, -1, "table", caption + "\n" + table_text(rows), rows=rows,
                                     table_id=f"table-{i}", verification_status="needs_review",
                                     review_reason="Verify table meaning and period against official page"))
            table.decompose()
        text = main.get_text("\n", strip=True)
        if text:
            blocks.append(make_block(source, -1, "text", text, extraction_method="html"))
        pages = [{"page": -1, "status": "extracted" if blocks else "blank", "blocks": len(blocks)}]
    elif suffix == ".txt":
        blocks = [make_block(source, -1, "text", path.read_text(encoding="utf-8"))]
        pages = [{"page": -1, "status": "extracted", "blocks": 1}]
    else:
        with Image.open(path) as image:
            text, words = ocr_image(image.convert("RGB"), state)
            rows = scanned_grid(image, words)
        blocks = [make_block(source, -1, "figure", text, rows=rows, asset=source["path"],
                             extraction_method="tesseract", verification_status="needs_review",
                             review_reason="Verify image labels, values and caption")]
        pages = [{"page": -1, "status": "needs_review", "blocks": 1}]
    result = {"source_id": source["id"], "source_sha256": source["sha256"], "pipeline_version": PIPELINE_VERSION,
              "extracted_at": now(), "blocks": blocks, "pages": pages}
    write_json(cache, result)
    return result


def extract_all(state: Path) -> dict:
    """Write a complete audit including failures, excluded sources and review-only blocks."""
    sources = read_json(state / "sources.json", {"sources": []})["sources"]
    reviews = read_json(state / "reviews.json", {})
    output, reports, seen = [], [], set()
    for source in sources:
        if source.get("source_status") == "retired":
            reports.append({"source_id":source["id"],"status":"retired"})
            continue
        if not source.get("path") or source.get("verification_status") == "discovery_only":
            continue
        # Prefer one canonical alias for identical documents.
        if source["sha256"] in seen:
            reports.append({"source_id": source["id"], "status": "duplicate"})
            continue
        seen.add(source["sha256"])
        print("extract", source["title"], flush=True)
        try:
            result = extract_source(source, state)
            for original in result["blocks"]:
                block = {**original}
                from assistant.kb.provenance import PUBLIC_FIELDS
                for field in ("title", "years", "period", "programme", "historical", "topic", *PUBLIC_FIELDS):
                    if field in source:
                        block[field] = source[field]
                approved_source = source.get("verification_status", "").startswith("approved")
                if not approved_source:
                    block["verification_status"] = "needs_review"
                    block["review_reason"] = "Source scope/currentness requires verification"
                review = reviews.get(block["id"])
                if review and review.get("source_sha256") == source["sha256"]:
                    if not review.get("reviewer") or not review.get("reviewed_at"):
                        raise ValueError("Review must name verifier and date")
                    for key in ("text", "years", "period", "rows", "programme", "historical", "kind", "topic", *PUBLIC_FIELDS, "related_evidence_block_ids"):
                        if key in review:
                            block[key] = review[key]
                    block["verification_status"] = review["status"]
                    block["reviewer"] = review["reviewer"]
                    block["reviewed_at"] = review["reviewed_at"]
                output.append(block)
            reports.append({"source_id": source["id"], "title": source["title"], "status": "processed", "pages": result["pages"]})
        except Exception as error:
            reports.append({"source_id": source["id"], "status": "error", "error": type(error).__name__})
    write_json(state / "blocks.json", output)
    report = {"generated_at": now(), "sources": reports, "blocks": len(output),
              "answerable_blocks": sum(b["verification_status"] in {"extracted", "approved"} and bool(b["text"]) for b in output),
              "pending_blocks": sum(b["verification_status"] == "needs_review" for b in output)}
    write_json(state / "extraction_report.json", report)
    return report
