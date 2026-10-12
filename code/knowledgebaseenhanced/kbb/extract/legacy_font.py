"""Legacy Hindi font decoding (KrutiDev / Chanakya / DevLys glyph text → Unicode).

These PDFs carry a complete text layer whose code points are Latin characters drawn with
Devanagari glyphs.  Decoding that layer is deterministic and keeps Docling's layout and
table structure.  ``lipi`` (MIT, ``pip install lipi-aparsoft``) reports ~85–92 % accuracy,
so decoded text is **never** trusted alone: it becomes read A, PaddleOCR-VL is read B, and
only agreement can produce ``machine_verified`` (doc 15 §3.2).
"""
from __future__ import annotations

import logging
import re
from copy import deepcopy

from ..models import Element
from ..tables import render_rows
from ..triage import KRUTI_PATTERNS, _legacy_score

log = logging.getLogger(__name__)
# Invalid Devanagari: a dependent vowel sign / virama / nukta at the start of a word.
_BAD_START = re.compile(r"(?:^|\s)[\u093e-\u094d\u0951-\u0957\u0962\u0963\u093c]")


def available() -> bool:
    try:
        import lipi  # noqa: F401
        return True
    except Exception:
        return False


def _convert(text: str, font: str) -> str:
    from lipi import HindiPreprocessor
    return HindiPreprocessor.convert(text, font_type=font)


def looks_legacy(text: str, ratio: float = 0.03) -> bool:
    return bool(KRUTI_PATTERNS.search(text)) or _legacy_score(text) >= ratio


def validity(text: str) -> float:
    """Share of Devanagari words that do not start with a dependent sign (cheap sanity)."""
    toks = re.findall(r"[\u0900-\u097f]+", text)
    if not toks:
        return 0.0
    bad = len(_BAD_START.findall(" " + " ".join(toks)))
    return 1.0 - bad / len(toks)


def decode_elements(elements: list[Element], font: str = "krutidev", min_validity: float = 0.9) -> tuple[list[Element], dict]:
    """Decode legacy-looking text in elements (and table cells).  Returns (elements, report)."""
    out, decoded, rejected = [], 0, 0
    for el in elements:
        el = deepcopy(el)
        if el.table is not None:
            changed = False
            for cell in el.table.cells:
                if cell.text and looks_legacy(cell.text, 0.0):
                    cell.text = _convert(cell.text, font)
                    changed = True
            if changed:
                el.text = render_rows(el.table)
                el.reader = "lipi+" + el.reader
                el.attrs["decoded"] = font
                decoded += 1
        elif el.text and looks_legacy(el.text):
            new = _convert(el.text, font)
            if validity(new) >= min_validity:
                el.attrs["legacy_raw"] = el.text[:2000]
                el.text = new
                el.reader = "lipi+" + el.reader
                el.attrs["decoded"] = font
                decoded += 1
            else:
                el.attrs["decode_rejected"] = True
                rejected += 1
        out.append(el)
    return out, {"decoded": decoded, "rejected": rejected, "font": font}
