"""Docling reader (MIT): born-digital PDFs, office files, and OCR mode for the second read.

Modes
-----
``native``  layout model + TableFormer on the PDF text layer, no OCR.  Primary reader for
            native pages.  CPU-friendly; no VRAM contention with the chat model.
``ocr``     same layout/table models but text from Tesseract (``eng+hin``) on rendered page
            images, full-page OCR forced.  Architecturally independent from PaddleOCR-VL, so
            it is the *second read* for scanned/legacy pages and yields its own table grid —
            which is what makes keyed-cell agreement possible (doc 15 §3.4).
``office``  DOCX / PPTX / XLSX / HTML through Docling's declarative backends.

Converters are created once per process (models load once) and long PDFs are converted in
page windows (``extract.docling_page_batch``) to bound memory on 100+ page reports.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from ..config import Config
from ..models import Cell, Element, Table
from ..textnorm import clean
from . import mk

log = logging.getLogger(__name__)

LABEL_MAP = {
    "title": "title", "section_header": "heading", "text": "paragraph", "paragraph": "paragraph",
    "reference": "paragraph", "list_item": "list_item", "table": "table", "document_index": "table",
    "picture": "figure", "chart": "figure", "caption": "caption", "footnote": "footnote",
    "page_header": "page_header", "page_footer": "page_footer", "formula": "formula", "code": "code",
    "key_value_region": "kv", "form": "kv", "checkbox_selected": "paragraph",
    "checkbox_unselected": "paragraph", "handwritten_text": "paragraph", "empty_value": "paragraph",
}


@lru_cache(maxsize=4)
def _converter(mode: str, table_mode: str, langs: str, tessdata: str, timeout: int, threads: int, device: str):
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_table_structure = True
    opts.table_structure_options.mode = TableFormerMode.ACCURATE if table_mode == "accurate" else TableFormerMode.FAST
    opts.table_structure_options.do_cell_matching = mode == "native"   # native: snap to PDF cells
    opts.document_timeout = timeout
    opts.accelerator_options = AcceleratorOptions(
        num_threads=threads, device={"cpu": AcceleratorDevice.CPU, "cuda": AcceleratorDevice.CUDA}.get(device, AcceleratorDevice.AUTO))
    if mode == "ocr":
        from docling.datamodel.pipeline_options import TesseractCliOcrOptions
        if tessdata:
            os.environ.setdefault("TESSDATA_PREFIX", tessdata)
        opts.do_ocr = True
        opts.ocr_options = TesseractCliOcrOptions(lang=langs.split("+"), force_full_page_ocr=True)
    else:
        opts.do_ocr = False
    fmt = PdfFormatOption(pipeline_options=opts)
    return DocumentConverter(format_options={InputFormat.PDF: fmt,
                                             InputFormat.IMAGE: ImageFormatOption(pipeline_options=opts)})


def converter(cfg: Config, mode: str):
    device = "cpu" if mode != "native" and cfg.runtime.device == "auto" else cfg.runtime.device
    return _converter(mode, cfg.extract.docling_table_mode, cfg.extract.tesseract_langs,
                      str(cfg.paths.tessdata or ""), cfg.extract.docling_timeout_s,
                      max(1, (os.cpu_count() or 2) // max(1, cfg.runtime.docling_workers)), device)


def _label(item) -> str:
    label = getattr(item, "label", "")
    return str(getattr(label, "value", label))


def _bbox(doc, prov) -> list[float] | None:
    try:
        height = doc.pages[prov.page_no].size.height
        b = prov.bbox.to_top_left_origin(page_height=height)
        return [round(float(b.l), 2), round(float(b.t), 2), round(float(b.r), 2), round(float(b.b), 2)]
    except Exception:
        return None


def _table(item, doc) -> Table:
    data = item.data
    cells = []
    for c in data.table_cells:
        cells.append(Cell(row=c.start_row_offset_idx, col=c.start_col_offset_idx, text=clean(c.text),
                          row_span=max(1, c.row_span), col_span=max(1, c.col_span),
                          is_col_header=bool(getattr(c, "column_header", False)),
                          is_row_header=bool(getattr(c, "row_header", False))))
    caption = ""
    try:
        caption = clean(item.caption_text(doc))
    except Exception:
        pass
    return Table(int(data.num_rows), int(data.num_cols), cells, caption)


def doc_to_elements(doc, *, reader: str, page_offset: int = 0, page_map: dict[int, int] | None = None) -> list[Element]:
    """DoclingDocument → Elements (reading order preserved)."""
    from ..tables import render_rows
    out: list[Element] = []
    for item, _depth in doc.iterate_items():
        label = _label(item)
        etype = LABEL_MAP.get(label)
        if etype is None:
            continue
        prov = item.prov[0] if getattr(item, "prov", None) else None
        page = (prov.page_no + page_offset) if prov else -1
        if page_map and prov:
            page = page_map.get(prov.page_no, page)
        bbox = _bbox(doc, prov) if prov else None
        if etype == "table":
            table = _table(item, doc)
            if table.n_rows == 0:
                continue
            out.append(mk("table", page, render_rows(table), bbox=bbox, table=table, reader=reader))
            continue
        text = clean(getattr(item, "text", "") or "")
        if etype == "figure":
            try:
                text = clean(item.caption_text(doc)) or text
            except Exception:
                pass
            out.append(mk("figure", page, text, bbox=bbox, reader=reader))
            continue
        if not text:
            continue
        level = None
        if etype == "title":
            level = 1
        elif etype == "heading":
            level = min(6, 1 + int(getattr(item, "level", 1) or 1))
        attrs = {}
        if etype == "list_item":
            attrs = {"marker": getattr(item, "marker", ""), "enumerated": bool(getattr(item, "enumerated", False))}
        if prov and len(item.prov) > 1:
            attrs["pages"] = sorted({p.page_no + page_offset for p in item.prov})
        out.append(mk("heading" if etype == "title" else etype, page, text, bbox=bbox, level=level,
                      reader=reader, **attrs))
    return out


def read_pdf_native(cfg: Config, path: str, pages: list[int]) -> dict[int, list[Element]]:
    """Run Docling on the given 1-based pages (contiguous windows), return elements per page."""
    from docling.datamodel.base_models import ConversionStatus
    conv = converter(cfg, "native")
    wanted = sorted(set(pages))
    out: dict[int, list[Element]] = {p: [] for p in wanted}
    windows: list[tuple[int, int]] = []
    for p in wanted:                         # contiguous runs, capped at batch size
        if windows and p == windows[-1][1] + 1 and p - windows[-1][0] < cfg.extract.docling_page_batch:
            windows[-1] = (windows[-1][0], p)
        else:
            windows.append((p, p))
    for start, end in windows:
        res = conv.convert(path, page_range=(start, end), raises_on_error=False)
        if res.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            log.warning("docling failed on %s pages %d-%d: %s", path, start, end, res.status)
            continue
        for el in doc_to_elements(res.document, reader="docling"):
            if el.page in out:
                out[el.page].append(el)
    return out


def read_images_ocr(cfg: Config, images: dict[int, str], scale: float) -> dict[int, list[Element]]:
    """Second read: Docling layout/TableFormer + Tesseract on page images.

    ``scale`` converts image pixels → PDF points (72/dpi) so bboxes align with read A.
    """
    from docling.datamodel.base_models import ConversionStatus
    conv = converter(cfg, "ocr")
    out: dict[int, list[Element]] = {}
    for page, img in images.items():
        res = conv.convert(img, raises_on_error=False)
        if res.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            out[page] = []
            continue
        els = doc_to_elements(res.document, reader="docling-tesseract")
        for el in els:
            el.page = page
            if el.bbox:
                el.bbox = [round(v * scale, 2) for v in el.bbox]
        out[page] = els
    return out


def read_office(cfg: Config, path: str) -> list[Element]:
    """DOCX / PPTX / XLSX via Docling backends.  Slides/sheets map to ``page`` when known."""
    conv = converter(cfg, "native")
    res = conv.convert(path, raises_on_error=True)
    return doc_to_elements(res.document, reader="docling-office")
