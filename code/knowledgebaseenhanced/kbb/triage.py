"""Stage 1 — per-page triage: send every page down the cheapest *correct* route.

Routes
------
``native``       good text layer                         → Docling (A); optional VLM cross-read for tables
``legacy_font``  KrutiDev/Chanakya/DevLys glyph text     → Docling layout + lipi decode (A), PaddleOCR-VL (B)
``scanned``      little/no text, large image coverage    → PaddleOCR-VL (A), Docling+Tesseract (B)
``broken_text``  (cid:)/U+FFFD/control chars in text     → same as scanned
``blank``        nothing on the page                     → recorded, produces no elements
``image``        image file                              → same as scanned
``pageless``     HTML / DOCX / PPTX / XLSX / TXT         → format reader

Every page gets a class; nothing is silently dropped (acceptance criterion).  Uses
pypdfium2 only (fast C library): ~2–5 ms/page, so triage of thousands of pages is seconds.
"""
from __future__ import annotations

import ctypes
import re
from dataclasses import asdict

from .config import Config
from .models import PageInfo
from .textnorm import DEVANAGARI_DIGITS, devanagari_share

# Frequent Hindi function words as they appear when KrutiDev glyph codes are read as Latin:
# के=ds की=dh का=dk है=gS में=esa को=dks से=ls और=vkSj लिए=fy, था=Fkk तथा=rFkk हैं=gSa पर=ij भी=Hkh
KRUTI_WORDS = {"ds", "dh", "dk", "gs", "esa", "dks", "ls", "vksj", "fy,", "fkk", "rfkk", "gsa", "ij",
               "hkh", "fd", ";g", "bl", "mu", "tks", "dj", "x;k", "gks", "ugha", "fd;k"}
KRUTI_PATTERNS = re.compile(r"Nk=o|vk;qDr|fuEukuqlkj|lwpuk|izos'k|ijh\{kk|fo'ofo|egkfo|\bgS\b|\besa\b")


def _font_names(textpage, n_chars: int, samples: int = 120) -> list[str]:
    import pypdfium2.raw as raw
    names: set[str] = set()
    if not n_chars:
        return []
    buf = ctypes.create_string_buffer(256)
    flags = ctypes.c_int()
    step = max(1, n_chars // samples)
    for i in range(0, n_chars, step):
        if raw.FPDFText_GetFontInfo(textpage.raw, i, buf, 256, ctypes.byref(flags)):
            name = buf.value.decode("latin-1", "replace")
            names.add(name.split("+", 1)[-1])     # drop subset prefix "AAAAAA+"
    return sorted(names)


def _legacy_score(text: str) -> float:
    toks = re.findall(r"\S+", text.casefold())
    if not toks:
        return 0.0
    return sum(t.strip(".:;") in KRUTI_WORDS for t in toks) / len(toks)


def classify_page(cfg: Config, page, page_no: int) -> PageInfo:
    import pypdfium2.raw as raw
    t = cfg.triage
    width, height = page.get_size()
    area = max(1.0, width * height)
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_bounded() or ""
        n_chars = textpage.count_chars()
        fonts = _font_names(textpage, n_chars)
    finally:
        textpage.close()
    meaningful = len(re.sub(r"[\W_]", "", text))
    img_area, paths, figure = 0.0, 0, False
    for obj in page.get_objects(filter=(raw.FPDF_PAGEOBJ_IMAGE, raw.FPDF_PAGEOBJ_PATH), max_depth=4):
        if obj.type == raw.FPDF_PAGEOBJ_IMAGE:
            left, bottom, right, top = obj.get_bounds()
            w, h = max(0.0, min(right, width) - max(left, 0)), max(0.0, min(top, height) - max(bottom, 0))
            img_area += w * h
            if w >= t.figure_min_area_pt[0] and h >= t.figure_min_area_pt[1]:
                figure = True
        else:
            paths += 1
    img_share = min(1.0, img_area / area)
    digits = sum(ch.isdigit() for ch in text.translate(DEVANAGARI_DIGITS))
    info = PageInfo(page=page_no, route="native", width=float(width), height=float(height),
                    chars=meaningful, devanagari_share=round(devanagari_share(text), 3),
                    image_area=round(img_share, 3), fonts=fonts[:20], has_figures=figure)
    info.table_heavy = (meaningful > 0 and digits / max(1, meaningful) >= t.table_digit_ratio
                        and paths >= t.table_min_paths)
    broken = any(m in text for m in t.broken_markers)
    legacy = (any(re.search(t.legacy_font_names, f) for f in fonts)
              or bool(KRUTI_PATTERNS.search(text))
              or _legacy_score(text) >= t.legacy_function_word_ratio and meaningful > 200)

    if meaningful == 0 and img_share < 0.02:
        info.route = "blank"
    elif legacy:
        info.route = "legacy_font"
        info.flags.append("legacy_font")
    elif broken and meaningful < 400:
        info.route = "broken_text"
        info.flags.append("broken_text_layer")
    elif meaningful < t.native_min_chars and (img_share >= t.scanned_image_area or meaningful == 0):
        info.route = "scanned"
    elif meaningful < t.native_min_chars:
        info.route = "scanned"
        info.flags.append("low_text_small_images")
    else:
        info.route = "native"
        if broken:
            info.flags.append("partly_broken_text")       # native but verify via OCR
        if img_share >= 0.5:
            info.flags.append("text_over_large_image")    # maybe OCR'd PDF; verify coverage
    return info


def triage_pdf(cfg: Config, path: str) -> list[PageInfo]:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    pages: list[PageInfo] = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                pages.append(classify_page(cfg, page, i + 1))
            except Exception as exc:  # a corrupt page must still be accounted for
                pages.append(PageInfo(page=i + 1, route="scanned", flags=[f"triage_error:{type(exc).__name__}"]))
            finally:
                page.close()
    finally:
        pdf.close()
    return pages


def triage_doc(cfg: Config, doc) -> list[dict]:
    """Return a list of ``PageInfo`` dicts for any registered format."""
    from .convert import effective_format
    fmt, path = effective_format(cfg, doc)
    if fmt == "pdf":
        pages = triage_pdf(cfg, path)
    elif fmt == "image":
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        pages = [PageInfo(page=1, route="image", width=float(w), height=float(h), image_area=1.0)]
    else:
        pages = [PageInfo(page=-1, route="pageless", flags=[f"format:{fmt}"])]
    return [asdict(p) for p in pages]


def routes_summary(pages: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in pages:
        out[p["route"]] = out.get(p["route"], 0) + 1
    return out
