"""Stage 4 — deterministic assembly and structure patches.

Principles (from 14 §3.2 & 15 §4):
- Heuristics resolve cross-page paragraph splits, consecutive table continuation,
  and running headers/footers.
- Optional LLM structure patches propose operations strictly over element IDs:
  `{"op": "set_heading", "id": "e12", "level": 2}` or `{"op": "pair_qa", ...}`.
  The applier NEVER accepts text from the LLM, eliminating fact alteration by design.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from .config import Config
from .models import Cell, Element, Table
from .tables import detect_headers, render_rows
from .textnorm import clean

log = logging.getLogger(__name__)

TERMINAL_PUNCT = {".", "!", "?", ":", ";", "।", "॥"}


def assemble_structure(cfg: Config, elements: list[Element], pages_count: int) -> list[Element]:
    """Apply deterministic structural merging and cleanup."""
    if not elements:
        return []

    # 1. Strip repetitive running headers and footers
    elements = _strip_running_headers_footers(elements, pages_count, cfg.structure.repeated_line_page_share)

    # 2. Join paragraphs broken across page boundaries
    elements = _join_cross_page_paragraphs(elements)

    # 3. Merge tables split across page boundaries
    elements = _merge_cross_page_tables(elements)

    # 4. Standardize heading levels and FAQ Q&A pairing
    elements = _apply_structural_heuristics(elements)

    return elements


def _strip_running_headers_footers(elements: list[Element], pages_count: int, share_thresh: float) -> list[Element]:
    """Remove lines appearing at page boundaries on >= 60% of pages."""
    if pages_count < 3:
        return [el for el in elements if el.type not in {"page_header", "page_footer"}]

    page_first_lines: dict[str, set[int]] = {}
    page_last_lines: dict[str, set[int]] = {}

    page_map: dict[int, list[Element]] = {}
    for el in elements:
        if el.page > 0:
            page_map.setdefault(el.page, []).append(el)

    for p, p_els in page_map.items():
        if p_els:
            page_first_lines.setdefault(clean(p_els[0].text), set()).add(p)
            page_last_lines.setdefault(clean(p_els[-1].text), set()).add(p)

    thresh = max(2, int(pages_count * share_thresh))
    strip_texts = {t for t, ps in page_first_lines.items() if len(ps) >= thresh and len(t) < 120}
    strip_texts.update({t for t, ps in page_last_lines.items() if len(ps) >= thresh and len(t) < 120})

    out = []
    for el in elements:
        if el.type in {"page_header", "page_footer"}:
            continue
        if clean(el.text) in strip_texts and el.type in {"paragraph", "heading"}:
            continue
        out.append(el)
    return out


def _join_cross_page_paragraphs(elements: list[Element]) -> list[Element]:
    """Join paragraphs split across page boundaries when sentence doesn't terminate."""
    out: list[Element] = []
    for el in elements:
        if not out:
            out.append(el)
            continue

        prev = out[-1]
        # Check if previous element is a paragraph on page N, current is a paragraph on page N+1
        if (
            prev.type == "paragraph"
            and el.type == "paragraph"
            and prev.page > 0
            and el.page == prev.page + 1
            and prev.text.strip()
            and el.text.strip()
        ):
            prev_last_char = prev.text.strip()[-1]
            next_first_char = el.text.strip()[0]

            # If previous ended without terminal punct and next starts with lowercase or continuation
            if prev_last_char not in TERMINAL_PUNCT and (next_first_char.islower() or prev_last_char in {",", "-", "("}):
                prev.text = prev.text.rstrip() + " " + el.text.lstrip()
                prev.attrs.setdefault("pages", [prev.page]).append(el.page)
                continue

        out.append(el)
    return out


def _merge_cross_page_tables(elements: list[Element]) -> list[Element]:
    """Merge continuous tables spanning consecutive pages."""
    out: list[Element] = []
    for el in elements:
        if not out:
            out.append(el)
            continue

        prev = out[-1]
        if (
            prev.type == "table"
            and el.type == "table"
            and prev.table
            and el.table
            and prev.page > 0
            and el.page == prev.page + 1
            and prev.table.n_cols == el.table.n_cols
        ):
            # Check if second table repeats headers or directly continues
            t1, t2 = prev.table, el.table
            grid1, grid2 = t1.grid(), t2.grid()
            hr, _ = detect_headers(t1)

            # If grid2 repeats header row, skip it
            rows2 = grid2[hr:] if (hr > 0 and len(grid2) > hr and grid2[:hr] == grid1[:hr]) else grid2
            merged_rows = grid1 + rows2

            merged_table = Table.from_grid(merged_rows, caption=t1.caption or t2.caption)
            prev.table = merged_table
            prev.text = render_rows(merged_table)
            prev.attrs.setdefault("pages", [prev.page]).append(el.page)
            continue

        out.append(el)
    return out


def _apply_structural_heuristics(elements: list[Element]) -> list[Element]:
    """Detect FAQ Q&A pairs and normalize heading levels."""
    out: list[Element] = []
    for el in elements:
        # Check FAQ patterns
        q_match = re.match(r"^(?:Q\.|Q\s*\d+\.?|Question\s*\d*[:.]?|प्रश्न\s*\d*[:.]?)\s*(.*)", el.text, re.I)
        if q_match and el.type in {"paragraph", "heading"}:
            el.type = "heading"
            el.level = 3
            el.attrs["is_faq_q"] = True

        # Check label-value layouts (e.g. "Last date ........ 15 July 2026")
        if el.type == "paragraph" and re.search(r"(\.{3,}|_{3,}|\t)\s*", el.text):
            parts = re.split(r"(\.{3,}|_{3,}|\t)\s*", el.text)
            if len(parts) >= 3:
                k, v = parts[0].strip(), parts[-1].strip()
                if len(k) < 80 and len(v) < 120:
                    el.type = "kv"
                    el.text = f"{k}: {v}"

        out.append(el)
    return out


def apply_llm_patches(elements: list[Element], patches: list[dict[str, Any]]) -> list[Element]:
    """Apply verified LLM structure patches.

    Patches can ONLY modify element types, heading levels, or group Q&A pairs.
    They are structurally FORBIDDEN from altering text characters.
    """
    el_map = {el.id: el for el in elements}

    for patch in patches:
        op = patch.get("op")
        target_id = patch.get("id")

        if op == "set_heading" and target_id in el_map:
            el = el_map[target_id]
            level = int(patch.get("level", 2))
            el.type = "heading"
            el.level = max(1, min(6, level))

        elif op == "pair_qa":
            q_id = patch.get("question")
            if q_id in el_map:
                el_map[q_id].type = "heading"
                el_map[q_id].level = 3
                el_map[q_id].attrs["is_faq_q"] = True

        elif op == "as_kv" and target_id in el_map:
            el = el_map[target_id]
            el.type = "kv"

    return elements
