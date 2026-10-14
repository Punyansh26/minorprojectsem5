"""Integration and Unit Tests for IIIT Naya Raipur RAG Bot and Grounding Layer."""
from __future__ import annotations

from pathlib import Path
import unittest

from kbb.bot import RAGBot
from kbb.config import get_config
from kbb.facts import query_facts
from kbb.retrieve import KnowledgeRetriever
from kbb.store import read_json


class TestRAGBot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_config()
        latest = read_json(cls.cfg.work / "latest_build.json", {})
        assert latest and "path" in latest, "Active index build must exist"
        cls.index_dir = Path(latest["path"])
        cls.bot = RAGBot(cls.cfg, cls.index_dir)
        cls.db_path = cls.index_dir / "facts.sqlite"

    def test_structured_fee_queries(self):
        facts = query_facts(self.db_path, "What is the tuition fee and hostel fee?")
        self.assertGreater(len(facts), 0)
        fact_text = facts[0]["text"]
        self.assertIn("90,000", fact_text)
        self.assertIn("15,000", fact_text)

    def test_structured_seat_matrix_queries(self):
        facts = query_facts(self.db_path, "How many seats are available in CSE?")
        self.assertGreater(len(facts), 0)
        fact_text = facts[0]["text"]
        self.assertIn("90", fact_text)
        self.assertIn("B.Tech CSE", fact_text)

    def test_structured_key_dates_queries(self):
        facts = query_facts(self.db_path, "When is the orientation program and Mid Term Examinations?")
        self.assertGreater(len(facts), 0)
        fact_text = facts[0]["text"]
        self.assertIn("August 20, 2026", fact_text)
        self.assertIn("November 03, 2026", fact_text)

    def test_structured_faculty_queries(self):
        facts = query_facts(self.db_path, "What is the email of Abhishek Sharma?")
        self.assertGreater(len(facts), 0)
        fact_text = facts[0]["text"]
        self.assertIn("abhishek[at]iiitnr.edu.in", fact_text)
        self.assertIn("ECE", fact_text)

    def test_structured_placement_queries(self):
        facts = query_facts(self.db_path, "What are the placement statistics and average package?")
        self.assertGreater(len(facts), 0)
        fact_text = facts[0]["text"]
        self.assertIn("30.34 LPA", fact_text)
        self.assertIn("14.50 LPA", fact_text)
        self.assertIn("Amazon", fact_text)

    def test_bot_extractive_fallback(self):
        # Force extractive synthesis by searching evidence
        ev_list = self.bot.retriever.search("B.Tech tuition fee", top_k=2)
        ans = self.bot._extractive_synthesis("B.Tech tuition fee", ev_list)
        self.assertIn("90,000", ans)
        self.assertIn("[S1]", ans)

    def test_bot_end_to_end_answer(self):
        resp = self.bot.ask("What is the total fee for Semester I of B.Tech?")
        self.assertIn(resp.mode, ["llm_grounded", "extractive_fallback"])
        clean_ans = resp.answer.replace(" ", "").replace(",", "")
        self.assertIn("181000", clean_ans)
        self.assertGreater(len(resp.citations), 0)
        self.assertEqual(resp.citations[0].id, "[S1]")
        self.assertEqual(resp.citations[0].page, 11)


if __name__ == "__main__":
    unittest.main()
