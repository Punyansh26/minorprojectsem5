"""The standalone bot reads the active release: exact facts, correct pages, no LLM needed for these checks."""
from __future__ import annotations

import os
import unittest

from kbb.config import get_config
from kbb.retrieve import ReleaseRetriever, active_release_root

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")


@unittest.skipUnless((get_config().work / "serving" / "active.json").exists(), "no active kbb release")
class TestReleaseRetriever(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_config()
        cls.retriever = ReleaseRetriever(cls.cfg, active_release_root(cls.cfg))

    def test_fee_question_cites_the_fee_page(self):
        hits = self.retriever.search("What is the B.Tech tuition fee?", top_k=4)
        fee = next(h for h in hits if "90000" in h.text)
        self.assertEqual(fee.page_start, 11)
        self.assertTrue(fee.source_file.endswith("B TECH_2026.pdf"))
        self.assertEqual(fee.status, "approved")

    def test_semester_total_is_printed_value_not_computed(self):
        hits = self.retriever.search("What is the total fee for Semester I of B.Tech?", top_k=4)
        self.assertTrue(any("1,81,000" in h.text.replace(" ", "") for h in hits))

    def test_calendar_dates_come_from_reviewed_calendar(self):
        hits = self.retriever.search("When are the mid term examinations?", top_k=4)
        self.assertTrue(any("October 26-November 03" in h.text for h in hits))

    def test_placement_headline_matches_the_slide_not_a_placeholder(self):
        hits = self.retriever.search("What is the highest CTC in placements?", top_k=4)
        text = "\n".join(h.text for h in hits)
        self.assertIn("120 LPA", text)
        self.assertNotIn("Top tier competitive offers", text)

    def test_unreviewed_documents_are_not_served(self):
        for h in self.retriever.search("slide presentation campus overview", top_k=6):
            self.assertIn(h.status, {"approved", "extracted", "machine_verified"})

    def test_missing_rank_returns_nothing(self):
        self.assertEqual(self.retriever.search("What is the 2026 CSE SC NTPC opening rank?", top_k=4), [])


if __name__ == "__main__":
    unittest.main()
