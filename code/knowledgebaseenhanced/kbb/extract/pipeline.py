"""Stage 2 — extraction pipeline orchestrator.

Routes each page/file through the cheapest correct reader, conducts independent
second reads for OCR/legacy pages, runs deterministic legacy font decoding, and
produces canonical Elements and SecondReads.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config import Config
from ..convert import effective_format
from ..models import Element, PageInfo, SecondRead
from ..render import image_source_path, render_pages
from ..store import KVCache
from ..triage import triage_doc
from . import docling_reader, html_reader, legacy_font, paddle_reader, tesseract_reader, text_reader

log = logging.getLogger(__name__)


def extract_document(cfg: Config, doc: Any, cache: KVCache) -> tuple[list[Element], list[SecondRead], list[PageInfo]]:
    """Extract all elements from a registered document."""
    fmt, effective_path = effective_format(cfg, doc)
    pages_raw = triage_doc(cfg, doc)
    pages_info = [PageInfo(**p) for p in pages_raw]

    elements: list[Element] = []
    second_reads: list[SecondRead] = []

    if fmt == "pdf":
        elements, second_reads = _extract_pdf(cfg, effective_path, doc.sha256, pages_info, cache)
    elif fmt == "image":
        elements, second_reads = _extract_image(cfg, effective_path, doc.sha256, cache)
    elif fmt == "html":
        elements = html_reader.read_html(cfg, effective_path)
    elif fmt in {"docx", "pptx", "xlsx"} and docling_reader.converter(cfg, "native"):
        try:
            elements = docling_reader.read_office(cfg, effective_path)
        except Exception as exc:
            log.warning("Docling office read failed for %s: %s; falling back to text reader", effective_path, exc)
            elements = text_reader.read_structured_file(cfg, fmt, effective_path)
    elif fmt in {"csv", "json", "yaml", "email", "text"}:
        elements = text_reader.read_structured_file(cfg, fmt, effective_path)
    else:
        # Generic text fallback
        elements = text_reader.read_markdown_text(cfg, effective_path)

    # Global ordering and element ID assignment
    elements = _assign_ids(elements, doc.doc_id)
    return elements, second_reads, pages_info


def _extract_pdf(cfg: Config, pdf_path: str, sha256: str, pages: list[PageInfo], cache: KVCache) -> tuple[list[Element], list[SecondRead]]:
    """Handle multi-page PDF with per-page routing."""
    elements_by_page: dict[int, list[Element]] = {p.page: [] for p in pages}
    second_reads: list[SecondRead] = []

    native_pages = [p.page for p in pages if p.route == "native"]
    scanned_pages = [p.page for p in pages if p.route in {"scanned", "broken_text"}]
    legacy_pages = [p.page for p in pages if p.route == "legacy_font"]

    # 1. Native born-digital pages
    if native_pages:
        try:
            native_map = docling_reader.read_pdf_native(cfg, pdf_path, native_pages)
            for page_num, els in native_map.items():
                elements_by_page[page_num].extend(els)
        except Exception as exc:
            log.warning("Docling native read failed on %s: %s; routing to OCR", pdf_path, exc)
            scanned_pages.extend(native_pages)
            scanned_pages = sorted(set(scanned_pages))

    # 2. Legacy font pages (KrutiDev, Chanakya, DevLys)
    if legacy_pages:
        # Primary read A: Docling native + Lipi decoder
        native_map = docling_reader.read_pdf_native(cfg, pdf_path, legacy_pages)
        for page_num, els in native_map.items():
            decoded_els, report = legacy_font.decode_elements(els)
            elements_by_page[page_num].extend(decoded_els)

        # Second read B: PaddleOCR-VL or Tesseract for verification
        rendered_images = render_pages(cfg, pdf_path, sha256, legacy_pages, cfg.triage.ocr_dpi)
        for page_num in legacy_pages:
            img_path = str(rendered_images[page_num])
            sec_text, sec_words = tesseract_reader.ocr_words(cfg, img_path, scale=72.0 / cfg.triage.ocr_dpi)
            second_reads.append(SecondRead(page=page_num, reader="tesseract", text=sec_text, words=sec_words))

    # 3. Scanned / OCR pages (Dual read!)
    if scanned_pages:
        rendered_ocr = render_pages(cfg, pdf_path, sha256, scanned_pages, cfg.triage.ocr_dpi)
        vlm_images = {f"p{p:04d}": str(rendered_ocr[p]) for p in scanned_pages}

        paddle_ok = paddle_reader.available(cfg)
        scale = 72.0 / cfg.triage.ocr_dpi

        if paddle_ok:
            # Primary read A: PaddleOCR-VL
            try:
                vlm_results = paddle_reader.recognise(cfg, cache, vlm_images)
                for p in scanned_pages:
                    k = f"p{p:04d}"
                    row = vlm_results.get(k, {})
                    els = paddle_reader.to_elements(row, p, scale)
                    elements_by_page[p].extend(els)
            except Exception as exc:
                log.error("PaddleOCR-VL failed on %s: %s; falling back to Tesseract", pdf_path, exc)
                paddle_ok = False

        if not paddle_ok:
            # Fallback primary read: Tesseract
            for p in scanned_pages:
                img_path = str(rendered_ocr[p])
                txt, words = tesseract_reader.ocr_words(cfg, img_path, scale=scale)
                els = tesseract_reader.words_to_elements(words, p)
                elements_by_page[p].extend(els)

        # Independent Second Read (Read B) for all scanned pages
        for p in scanned_pages:
            img_path = str(rendered_ocr[p])
            sec_text, sec_words = tesseract_reader.ocr_words(cfg, img_path, scale=scale)
            second_reads.append(SecondRead(page=p, reader="tesseract", text=sec_text, words=sec_words))

    # Combine all pages in order
    all_elements: list[Element] = []
    for p in sorted(elements_by_page.keys()):
        all_elements.extend(elements_by_page[p])

    return all_elements, second_reads


def _extract_image(cfg: Config, image_path: str, sha256: str, cache: KVCache) -> tuple[list[Element], list[SecondRead]]:
    """Handle standalone image document with dual read."""
    norm_img = str(image_source_path(cfg, image_path, sha256))
    elements: list[Element] = []
    second_reads: list[SecondRead] = []

    paddle_ok = paddle_reader.available(cfg)
    if paddle_ok:
        try:
            res = paddle_reader.recognise(cfg, cache, {"p0001": norm_img})
            elements = paddle_reader.to_elements(res.get("p0001", {}), 1, scale=1.0)
        except Exception as exc:
            log.warning("PaddleOCR-VL failed on image %s: %s", image_path, exc)
            paddle_ok = False

    if not paddle_ok:
        txt, words = tesseract_reader.ocr_words(cfg, norm_img, scale=1.0)
        elements = tesseract_reader.words_to_elements(words, 1)

    # Independent second read
    sec_text, sec_words = tesseract_reader.ocr_words(cfg, norm_img, scale=1.0)
    second_reads.append(SecondRead(page=1, reader="tesseract", text=sec_text, words=sec_words))

    return elements, second_reads


def _assign_ids(elements: list[Element], doc_id: str) -> list[Element]:
    """Ensure every element has an ordered index, page coordinate consistency, and stable ID."""
    for idx, el in enumerate(elements, 1):
        el.id = f"e{idx}"
        el.order = idx
        if el.page is None:
            el.page = -1
    return elements
