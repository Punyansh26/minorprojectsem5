"""Chapter 04: the reranker may only reorder the fused shortlist, and every failure keeps fusion order."""
from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import spotcheck as sc  # noqa: E402
from kbb.release import ReleaseSearch  # noqa: E402
from kbb.rerank import Reranker  # noqa: E402


def keyword_scorer(word):
    """Fake cross-encoder: pairs whose text contains ``word`` score high."""
    return lambda: (lambda pairs: [10.0 if word in text else float(-i) for i, (_, text) in enumerate(pairs)])


class TestReranker(unittest.TestCase):
    def test_orders_by_score(self):
        r = Reranker("fake", loader=keyword_scorer("hostel"))
        order = r.rerank("q", [("a", "fees"), ("b", "hostel rules"), ("c", "library")])
        self.assertEqual(order, ["b", "a", "c"])
        self.assertEqual(r.last["status"], "ok")

    def test_missing_model_keeps_fusion_order(self):
        def broken():
            raise OSError("incomplete download")
        r = Reranker("fake", loader=broken)
        self.assertIsNone(r.rerank("q", [("a", "x"), ("b", "y")]))
        self.assertEqual(r.last["status"], "unavailable")
        self.assertIn("incomplete", r.last["reason"])

    def test_scoring_error_keeps_fusion_order(self):
        def loader():
            def score(pairs):
                raise RuntimeError("bad input")
            return score
        r = Reranker("fake", loader=loader)
        self.assertIsNone(r.rerank("q", [("a", "x"), ("b", "y")]))
        self.assertEqual(r.last["status"], "error")

    def test_budget_overrun_falls_back_and_blocks_pileup(self):
        release = threading.Event()

        def loader():
            def score(pairs):
                release.wait(5)
                return [0.0] * len(pairs)
            return score
        r = Reranker("fake", budget_s=0.05, loader=loader)
        started = time.monotonic()
        self.assertIsNone(r.rerank("q", [("a", "x"), ("b", "y")]))
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(r.last["status"], "timeout")
        # The abandoned job still runs, so the next query must not queue behind it.
        self.assertIsNone(r.rerank("q", [("a", "x"), ("b", "y")]))
        self.assertEqual(r.last["status"], "busy")
        release.set()

    def test_truncates_long_text_and_skips_single_candidate(self):
        seen = []

        def loader():
            def score(pairs):
                seen.extend(pairs)
                return [0.0] * len(pairs)
            return score
        r = Reranker("fake", max_chars=5, loader=loader)
        self.assertIsNone(r.rerank("q", [("a", "x")]))
        self.assertEqual(r.last["status"], "skipped")
        r.rerank("q", [("a", "abcdefghij"), ("b", "k")])
        self.assertEqual(seen[0], ("q", "abcde"))

    def test_equal_scores_keep_input_order(self):
        r = Reranker("fake", loader=lambda: (lambda pairs: [1.0] * len(pairs)))
        self.assertEqual(r.rerank("q", [("a", "x"), ("b", "y"), ("c", "z")]), ["a", "b", "c"])


def engine(reranker, parents):
    eng = ReleaseSearch.__new__(ReleaseSearch)      # no release files, no embedder
    eng.parents = parents
    eng.reranker = reranker
    eng.cfg = SimpleNamespace(retrieval=SimpleNamespace(rerank_top=2))
    return eng


def block(pid, years=()):
    return {"id": pid, "text": pid + " text", "verification_status": "extracted", "years": list(years)}


class TestReleaseRerankWiring(unittest.TestCase):
    def test_disabled_is_identity(self):
        eng = engine(None, {"a": block("a")})
        self.assertEqual(eng._rerank("q", ["a"], {}, set()), ["a"])

    def test_reorders_head_and_keeps_tail(self):
        parents = {p: block(p) for p in "abc"}
        eng = engine(Reranker("fake", loader=keyword_scorer("best")), parents)
        best_unit = {"a": (0.03, "plain"), "b": (0.02, "best row")}
        self.assertEqual(eng._rerank("q", ["a", "b", "c"], best_unit, set()), ["b", "a", "c"])

    def test_failure_keeps_fusion_order(self):
        def broken():
            raise OSError("no weights")
        eng = engine(Reranker("fake", loader=broken), {p: block(p) for p in "ab"})
        self.assertEqual(eng._rerank("q", ["a", "b"], {}, set()), ["a", "b"])

    def test_year_matched_block_stays_above_undated(self):
        parents = {"dated": block("dated", [2026]), "undated": block("undated")}
        eng = engine(Reranker("fake", loader=keyword_scorer("undated")), parents)
        best_unit = {"dated": (0.03, "dated"), "undated": (0.02, "undated")}
        self.assertEqual(eng._rerank("fee 2026", ["dated", "undated"], best_unit, {2026}), ["dated", "undated"])

    def test_ineligible_parents_are_not_sent_to_the_model(self):
        sent = []

        def loader():
            def score(pairs):
                sent.extend(t for _, t in pairs)
                return [0.0] * len(pairs)
            return score
        parents = {"a": block("a"), "b": {**block("b"), "verification_status": "rejected"}, "c": block("c")}
        engine(Reranker("fake", loader=loader), parents)._rerank("q", ["a", "b", "c"], {}, set())
        self.assertEqual(sent, ["a text", "c text"])


class Hit:
    def __init__(self, text, file, page):
        self.text, self.source_file, self.page_number, self.block_id = text, file, page, "b"


CASE = {"id": "c", "topic": "fees", "language": "hindi", "origin": "new", "expect": "answerable", "question": "fee?",
        "required_terms": ["90000"], "expected_sources": [{"file": "B TECH_2026.pdf", "page": 11}]}


class TestOrderingMetrics(unittest.TestCase):
    def test_reciprocal_rank_and_prefix_pass(self):
        hits = [Hit("other", "x.pdf", 1), Hit("Tuition 90000", "B TECH_2026.pdf", 11)]
        self.assertEqual(sc.reciprocal_rank(CASE, hits), 0.5)
        fields = sc.ordering_fields(CASE, hits)
        self.assertFalse(fields["pass_at_1"])
        self.assertTrue(fields["pass_at_3"])

    def test_no_source_or_not_answerable_has_no_rank(self):
        self.assertIsNone(sc.reciprocal_rank({**CASE, "expected_sources": []}, []))
        self.assertEqual(sc.ordering_fields({**CASE, "expect": "no_result"}, []), {})
        self.assertEqual(sc.reciprocal_rank(CASE, [Hit("x", "y.pdf", 2)]), 0.0)

    def test_summary_splits_by_language(self):
        rows = sc.run_engine([CASE, {**CASE, "id": "d", "language": "english"}],
                             lambda q, k: [Hit("Tuition 90000", "B TECH_2026.pdf", 11)])
        summary = sc.summarize(rows)
        self.assertEqual(summary["ordering"]["mrr"], 1.0)
        self.assertEqual(summary["by_language"]["hindi"]["pass_at_1"], 1)
        self.assertEqual(summary["by_language"]["english"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
