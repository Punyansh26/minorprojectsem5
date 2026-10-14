"""The spot-check runner scores hits, misses and wrong pages mechanically."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import spotcheck as sc  # noqa: E402


class Hit:
    def __init__(self, text, file, page):
        self.text, self.source_file, self.page_number, self.block_id = text, file, page, "b"


def case(**kw):
    base = {"id": "c", "topic": "fees", "language": "english", "origin": "new", "expect": "answerable",
            "required_terms": ["90000"], "expected_sources": [{"file": "B TECH_2026.pdf", "page": 11}]}
    return {**base, **kw}


class TestScoring(unittest.TestCase):
    def test_hit_with_right_page(self):
        r = sc.score_case(case(), [Hit("Tuition Fee | 90000", "admissions/B TECH_2026.pdf", 11)])
        self.assertEqual(r["status"], "pass")

    def test_miss_when_term_absent(self):
        r = sc.score_case(case(), [Hit("Hostel 15000", "admissions/B TECH_2026.pdf", 11)])
        self.assertEqual(r["status"], "fail")
        self.assertFalse(r["terms_ok"])

    def test_wrong_page_fails_even_if_term_found(self):
        r = sc.score_case(case(), [Hit("Tuition 90000", "admissions/B TECH_2026.pdf", 3)])
        self.assertEqual(r["status"], "fail")
        self.assertTrue(r["terms_ok"])
        self.assertFalse(r["source_ok"])

    def test_pageless_source_matches_any_page(self):
        c = case(expected_sources=[{"file": "JoSAA_2026_round_5.html", "page": -1}], required_terms=["15883"])
        self.assertEqual(sc.score_case(c, [Hit("closing 15883", "JoSAA_2026_round_5.html", -1)])["status"], "pass")

    def test_required_any_alternative_spellings(self):
        c = case(required_terms=[], required_any=["25,000", "25000"], expected_sources=[])
        self.assertEqual(sc.score_case(c, [Hit("Mess Advance 25000", "x.pdf", 1)])["status"], "pass")
        self.assertEqual(sc.score_case(c, [Hit("Mess Advance", "x.pdf", 1)])["status"], "fail")

    def test_no_result_requires_empty(self):
        c = case(expect="no_result", required_terms=[], expected_sources=[])
        self.assertEqual(sc.score_case(c, [])["status"], "pass")
        self.assertEqual(sc.score_case(c, [Hit("some rank", "j.html", -1)])["status"], "fail")

    def test_answer_review_is_not_scored(self):
        r = sc.score_case(case(expect="answer_review"), [])
        self.assertEqual(r["status"], "review")
        self.assertEqual(sc.summarize([r])["scored"], 0)

    def test_engine_crash_is_a_failure_not_a_skip(self):
        def boom(q, k):
            raise RuntimeError("index missing")
        rows = sc.run_engine([case()], boom)
        self.assertEqual(rows[0]["status"], "error")

    def test_compare_lists_regressions(self):
        ref = [{"id": "a", "topic": "t", "language": "l", "origin": "legacy", "expect": "answerable", "status": "pass"}]
        new = [{**ref[0], "status": "fail", "terms_ok": False, "source_ok": True}]
        report = sc.compare({"legacy": ref, "new": new})
        self.assertIn("regressions (1): a", report)


if __name__ == "__main__":
    unittest.main()
