"""Stage 5 — fidelity verification engine & machine_verified status assignment.

Checks (from 14 §3.1 & 15 §5):
1. Keyed Table Cells: compares (row_key, col_key, value) triples from Read A vs Read B.
2. Number Tokens: ensures all dates, currency, ranks, and percentages in Read A appear
   in Read B.
3. Word Coverage: verifies Read B words are recalled >= 93% (85% Devanagari) by Read A.
4. Critical Topic Gate: non-native content covering fees, deadlines, or eligibility
   always requires human review (`needs_review`), while agreeing general content
   becomes `machine_verified`.
"""
from __future__ import annotations

import logging
from typing import Any

from rapidfuzz import fuzz

from .config import Config
from .models import Element, SecondRead
from .tables import keyed_cells
from .textnorm import (
    contains_keyword,
    devanagari_share,
    norm_for_compare,
    number_multiset,
    number_tokens,
    words,
)

log = logging.getLogger(__name__)


def verify_document(
    cfg: Config,
    elements: list[Element],
    second_reads: list[SecondRead],
    doc_meta: dict[str, Any],
) -> tuple[list[Element], dict[str, Any]]:
    """Run all verification checks on document elements against second reads."""
    second_map: dict[int, SecondRead] = {sr.page: sr for sr in second_reads}
    report: dict[str, Any] = {
        "status": "passed",
        "elements_checked": len(elements),
        "numbers_checked": 0,
        "mismatches": 0,
        "tables_checked": 0,
        "table_disagreements": 0,
        "critical_escalations": 0,
        "review_pages": [],
        "failures": [],
    }

    is_critical_doc = contains_keyword(
        f"{doc_meta.get('title', '')} {doc_meta.get('topic', '')}", cfg.verify.critical_keywords
    )

    for el in elements:
        page_no = el.page
        sr = second_map.get(page_no)

        # 1. Born-digital native text without second read
        if sr is None or el.reader == "docling":
            el.status = "extracted"
            continue

        # Check critical content flag for this specific element
        is_critical_el = is_critical_doc or contains_keyword(el.text, cfg.verify.critical_keywords)

        # 2. Table Verification (Keyed Cells)
        if el.type == "table" and el.table:
            report["tables_checked"] += 1
            table_ok, diffs = _verify_table_keyed_cells(cfg, el.table, sr)
            if not table_ok:
                report["table_disagreements"] += 1
                el.status = "needs_review"
                el.reasons.append(f"Table keyed-cell disagreement: {len(diffs)} cells differed")
                report["failures"].append({"element_id": el.id, "page": page_no, "type": "table_diff", "diffs": diffs[:10]})
                report["review_pages"].append(page_no)
                continue

        # 3. Number Token Fidelity Check
        nums_a = number_tokens(el.text)
        report["numbers_checked"] += len(nums_a)
        if nums_a:
            num_ok, missing_nums = _verify_numbers(nums_a, sr.text)
            if not num_ok:
                report["mismatches"] += len(missing_nums)
                el.status = "needs_review"
                el.reasons.append(f"Number tokens missing from second read: {missing_nums}")
                report["failures"].append({"element_id": el.id, "page": page_no, "type": "number_mismatch", "missing": missing_nums})
                report["review_pages"].append(page_no)
                continue

        # 4. Coverage Check
        coverage_ok, cov_val = _verify_coverage(cfg, el.text, sr.text)
        if not coverage_ok:
            el.status = "needs_review"
            el.reasons.append(f"Word coverage too low ({cov_val:.2f})")
            report["failures"].append({"element_id": el.id, "page": page_no, "type": "low_coverage", "coverage": cov_val})
            report["review_pages"].append(page_no)
            continue

        # 5. Determine final status
        if is_critical_el:
            # Critical topics (fees, deadlines) from non-native source stay needs_review for safety
            el.status = "needs_review"
            el.reasons.append("Critical topic (fee/deadline/cutoff) requires human approval")
            report["critical_escalations"] += 1
            report["review_pages"].append(page_no)
        elif cfg.verify.allow_machine_verified:
            el.status = "machine_verified"
        else:
            el.status = "needs_review"

    # Global report status
    report["review_pages"] = sorted(set(report["review_pages"]))
    if report["mismatches"] > 0 or report["table_disagreements"] > 0:
        report["status"] = "needs_review"

    return elements, report


def _verify_table_keyed_cells(cfg: Config, table, sr: SecondRead) -> tuple[bool, list[dict]]:
    """Check that table cells match independent second read."""
    keys = keyed_cells(table)
    if not keys:
        return True, []

    # If second read has an extracted table, compare directly
    sr_tables = [e.table for e in sr.elements if e.type == "table" and e.table]
    if sr_tables:
        sr_keys = { (k.row_key, k.col_key): k.value_norm for k in keyed_cells(sr_tables[0]) }
        diffs = []
        for k in keys:
            norm_val = k.value_norm
            sr_val = sr_keys.get((k.row_key, k.col_key))
            if sr_val is None:
                # Fuzzy match on row/col keys
                matched = False
                for (sr_rk, sr_ck), v in sr_keys.items():
                    if fuzz.ratio(k.row_key, sr_rk) >= cfg.verify.key_fuzzy_ratio and fuzz.ratio(k.col_key, sr_ck) >= cfg.verify.key_fuzzy_ratio:
                        sr_val = v
                        matched = True
                        break
                if not matched:
                    diffs.append({"cell": (k.row_key, k.col_key), "expected": norm_val, "actual": "missing"})
                    continue

            if k.numeric:
                if norm_val != sr_val:
                    diffs.append({"cell": (k.row_key, k.col_key), "expected": norm_val, "actual": sr_val})
            else:
                if fuzz.ratio(norm_val, sr_val) < cfg.verify.text_cell_ratio:
                    diffs.append({"cell": (k.row_key, k.col_key), "expected": norm_val, "actual": sr_val})

        return (len(diffs) == 0), diffs

    # Fallback: ensure all cell numbers occur in the raw OCR text of second read
    diffs = []
    sr_num_set = set(number_tokens(sr.text))
    for k in keys:
        if k.numeric:
            cell_nums = set(number_tokens(k.value))
            if not cell_nums.issubset(sr_num_set):
                diffs.append({"cell": (k.row_key, k.col_key), "expected": k.value, "missing": list(cell_nums - sr_num_set)})

    return (len(diffs) == 0), diffs


def _verify_numbers(nums_a: list[str], sr_text: str) -> tuple[bool, list[str]]:
    """Ensure every number in Read A exists in Read B."""
    sr_nums = number_multiset(sr_text)
    missing = []
    for n in nums_a:
        if sr_nums[n] > 0:
            sr_nums[n] -= 1
        else:
            missing.append(n)
    return (len(missing) == 0), missing


def _verify_coverage(cfg: Config, text_a: str, sr_text: str) -> tuple[bool, float]:
    """Token recall of Read B words by Read A."""
    words_b = set(words(sr_text, drop_stop=True))
    if not words_b:
        return True, 1.0

    words_a = set(words(text_a, drop_stop=True))
    recalled = len(words_b & words_a) / len(words_b)

    thresh = cfg.verify.coverage_min_devanagari if devanagari_share(sr_text) > 0.4 else cfg.verify.coverage_min
    return (recalled >= thresh), recalled
