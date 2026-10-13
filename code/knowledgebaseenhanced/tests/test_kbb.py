"""Unit tests for the Knowledge Base Pipeline v2 (`kbb`)."""
from __future__ import annotations

import unittest
from kbb.config import get_config
from kbb.models import Cell, Element, PageInfo, SecondRead, Table
from kbb.tables import detect_headers, from_html, from_markdown, keyed_cells, render_rows
from kbb.textnorm import (
    clean,
    devanagari_share,
    norm_for_compare,
    number_multiset,
    number_tokens,
    words,
)
from kbb.verify import _verify_coverage, _verify_numbers, _verify_table_keyed_cells


class TestTextNorm(unittest.TestCase):
    def test_devanagari_digits(self):
        txt = "वर्ष २०२६ में फीस ₹१,२५,००० है"
        nums = number_tokens(txt)
        self.assertIn("125000", nums)
        self.assertIn("2026", nums)

    def test_date_tokens(self):
        txt = "Last date is 15/07/2026 and 15-08-2026."
        nums = number_tokens(txt)
        self.assertEqual(nums, ["15/7/2026", "15/8/2026"])

    def test_devanagari_share(self):
        self.assertGreater(devanagari_share("यह एक हिंदी वाक्य है"), 0.8)
        self.assertLess(devanagari_share("This is English text"), 0.1)


class TestTableKeyedCells(unittest.TestCase):
    def test_table_html_parsing_and_keyed_cells(self):
        html = """
        <table>
          <thead>
            <tr><th>Fee Type</th><th>General/OBC</th><th>SC/ST</th></tr>
          </thead>
          <tbody>
            <tr><td>Tuition</td><td>1,25,000</td><td>0</td></tr>
            <tr><td>Hostel</td><td>30,000</td><td>30,000</td></tr>
          </tbody>
        </table>
        """
        table = from_html(html)
        self.assertIsNotNone(table)
        self.assertEqual(table.n_rows, 3)
        self.assertEqual(table.n_cols, 3)

        keys = keyed_cells(table)
        self.assertEqual(len(keys), 4)

        # Check keyed cell triples
        k_map = {(k.row_key, k.col_key): k.value_norm for k in keys}
        self.assertEqual(k_map.get(("Tuition", "General/OBC")), "125000")
        self.assertEqual(k_map.get(("Tuition", "SC/ST")), "0")
        self.assertEqual(k_map.get(("Hostel", "General/OBC")), "30000")

    def test_swapped_column_detection(self):
        """Proof of fix for 14 §3.1: swapped column fails keyed-cell verification."""
        cfg = get_config()

        # Read A
        t_a = from_markdown("""
        | Fee Type | General/OBC | SC/ST |
        | --- | --- | --- |
        | Tuition | 1,25,000 | 0 |
        """)

        # Read B with swapped columns (SC/ST got 1,25,000)
        t_b = from_markdown("""
        | Fee Type | General/OBC | SC/ST |
        | --- | --- | --- |
        | Tuition | 0 | 1,25,000 |
        """)

        sr = SecondRead(page=1, reader="docling-tesseract", text="Tuition 0 1,25,000",
                        elements=[Element(id="e1", type="table", page=1, text="", table=t_b)])

        table_ok, diffs = _verify_table_keyed_cells(cfg, t_a, sr)
        self.assertFalse(table_ok)
        self.assertGreater(len(diffs), 0)


class TestFidelityChecks(unittest.TestCase):
    def test_number_verification(self):
        nums_a = ["125000", "2026"]
        sr_text = "The fees for 2026 is 1,25,000 rupees."
        ok, missing = _verify_numbers(nums_a, sr_text)
        self.assertTrue(ok)
        self.assertEqual(len(missing), 0)

        # Missing number
        nums_missing = ["125000", "99999"]
        ok, missing = _verify_numbers(nums_missing, sr_text)
        self.assertFalse(ok)
        self.assertEqual(missing, ["99999"])

    def test_coverage_verification(self):
        cfg = get_config()
        text_a = "BTech admission notice for academic year 2026"
        sr_text = "BTech admission notice 2026"
        ok, cov = _verify_coverage(cfg, text_a, sr_text)
        self.assertTrue(ok)
        self.assertGreaterEqual(cov, 0.9)


if __name__ == "__main__":
    unittest.main()
