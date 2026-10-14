"""Corpus audit: each defect type is detected and a clean document is not flagged."""
from __future__ import annotations

import unittest

from kbb.audit import audit_corpus, audit_text, flattened_table_runs, garble_ratio

FRONT = '---\ndoc_id: "d1"\ncategory: "general"\nsource_file: "general/x.{ext}"\n---\n\n'

CLEAN_BODY = "# Library\n\n<!-- page: 1 -->\n\n" + " ".join(
    ["The library is open from nine in the morning to eight in the evening on all working days."] * 8) + "\n"

CLEAN_HINDI = "संस्थान के पुस्तकालय में छात्रों के लिए सभी विषयों की पुस्तकें उपलब्ध हैं और यह प्रतिदिन खुला रहता है। " * 3


class TestAudit(unittest.TestCase):
    def codes(self, text: str) -> set[str]:
        return {i["code"] for i in audit_text(text)["issues"]}

    def test_clean_document_has_no_issues(self):
        text = FRONT.format(ext="html") + CLEAN_BODY + "\n" + CLEAN_HINDI
        self.assertEqual(self.codes(text), set())

    def test_heading_only_document_is_thin(self):
        text = FRONT.format(ext="html") + "# Campus Facilities, Helpline & Location Guidelines"
        self.assertIn("thin", self.codes(text))

    def test_garbled_devanagari_is_detected(self):
        # The brochure's real damage: conjunct glyphs dropped, leaving gaps and orphaned signs.
        garbled = ("डॉ. श्यामा प्रसाद मुखज  अंतररा ीय सूचना प्रौ ो गक  सं ान, नया रायपुर "
                   "ि वभाग ु कुलप त  ा ापक  संसाधन ा  ि ा नी त ") * 3
        ratio, n = garble_ratio(garbled)
        self.assertGreater(ratio, 0.06)
        self.assertIn("garbled_devanagari", self.codes(FRONT.format(ext="pdf") + CLEAN_BODY + garbled))

    def test_clean_hindi_not_flagged(self):
        ratio, _ = garble_ratio(CLEAN_HINDI)
        self.assertLess(ratio, 0.03)

    def test_flattened_fee_table_is_detected(self):
        flat = ("# V. B. Tech Fee Structure\n\nTuition Fee ₹ 90000.00\nAcademic and Student Welfare Fee ₹ 20000.00\n"
                "Hostel Fee ₹ 15, 000.00\nMess Advance ₹ 25, 000.00\nTotal Fee Semester I ₹ 1, 81, 000. 000\n")
        self.assertGreaterEqual(len(flattened_table_runs(flat)), 1)
        codes = self.codes(FRONT.format(ext="pdf") + CLEAN_BODY + flat)
        self.assertIn("flattened_table", codes)
        self.assertIn("ocr_number_noise", codes)

    def test_real_markdown_table_is_not_flattened(self):
        table = "| Fee | Amount |\n| --- | --- |\n| Tuition | 90000 |\n| Hostel | 15000 |\n| Mess | 25000 |\n| Welfare | 20000 |\n"
        self.assertEqual(flattened_table_runs(table), [])

    def test_pdf_without_page_anchors(self):
        body = "# Report\n\n" + "A sentence with enough words to be body text for the report. " * 12
        self.assertIn("missing_pages", self.codes(FRONT.format(ext="pdf") + body))
        self.assertNotIn("missing_pages", self.codes(FRONT.format(ext="html") + body))

    def test_synthesized_marker_flagged(self):
        text = FRONT.format(ext="html") + CLEAN_BODY + "\nThis summary of the slide was synthesized from the image.\n"
        self.assertIn("synthesized", self.codes(text))

    def test_corpus_report_lists_documents_needing_reextraction(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "general").mkdir()
            (root / "general" / "good.md").write_text(FRONT.format(ext="html") + CLEAN_BODY, encoding="utf-8")
            (root / "general" / "empty.md").write_text(FRONT.format(ext="html").replace("d1", "empty") + "# Title only", encoding="utf-8")
            report = audit_corpus(root, root / "report.json")
            self.assertEqual(report["documents"], 2)
            self.assertEqual(report["needs_reextraction"], ["empty"])
            self.assertTrue((root / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
