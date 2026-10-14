"""Honest statuses: scans stay needs_review until a recorded page review; reviews are exact and auditable."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kbb.corpus import base_page_status, load_document, split_pages
from kbb.reviews import ReviewError, apply_page_review, make_lookup

OCR_DOC = '---\ndoc_id: "g-guest"\ntitle: "Guest House"\nsource_file: "general/GuestHouse-1.pdf"\nreader: "tesseract-eng+hin"\nstatus: "needs_review"\n---\n\n# Guest House\n\n<!-- page: 1 -->\n\nA stay costs Rs. 2730.00/month and the right 10 get the room vacated.\n\n<!-- page: 2 -->\n\nTariff garbage |||\n'
HTML_DOC = '---\ndoc_id: "g-lib"\ntitle: "Library"\nsource_file: "general/Library.html"\n---\n\n# Library\n\nBooks: 7316 titles are available.\n'


def write(tmp: Path, name: str, text: str) -> Path:
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    return path


class TestStatuses(unittest.TestCase):
    def test_ocr_document_is_needs_review_until_reviewed(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            doc = load_document(write(tmp, "a.md", OCR_DOC), tmp, {})
            self.assertTrue(all(e.status == "needs_review" for e in doc.elements))

    def test_html_document_is_extracted_and_pageless(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "general").mkdir()
            (tmp / "general" / "Library.html").write_text("<html></html>")
            doc = load_document(write(tmp, "b.md", HTML_DOC), tmp, {})
            self.assertEqual({e.status for e in doc.elements}, {"extracted"})
            self.assertEqual({e.page for e in doc.elements}, {-1})

    def test_image_source_never_extracted(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            img = tmp / "slide.jpg"
            img.write_bytes(b"x")
            self.assertEqual(base_page_status({}, 1, [img], {}), "needs_review")

    def test_pdf_page_without_text_layer_is_needs_review(self):
        pdf = Path("/x/a.pdf")
        self.assertEqual(base_page_status({}, 2, [pdf], {pdf: ({1}, 2)}), "needs_review")
        self.assertEqual(base_page_status({}, 1, [pdf], {pdf: ({1}, 2)}), "extracted")

    def test_pageless_pdf_judged_by_text_layer_coverage(self):
        pdf = Path("/x/a.pdf")
        self.assertEqual(base_page_status({}, -1, [pdf], {pdf: ({1, 2, 3}, 4)}), "extracted")
        self.assertEqual(base_page_status({}, -1, [pdf], {pdf: ({1}, 4)}), "needs_review")

    def test_page_review_approves_with_exact_patch(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            review = {"doc_id": "g-guest", "page": 1, "decision": "approved", "reviewer": "agent",
                      "patches": [{"find": "right 10 get", "replace": "right to get"}]}
            doc = load_document(write(tmp, "a.md", OCR_DOC), tmp, {}, make_lookup([review]))
            page1 = [e for e in doc.elements if e.page == 1 and e.type == "paragraph"][0]
            self.assertIn("right to get", page1.text)
            self.assertEqual(page1.status, "approved")
            page2 = [e for e in doc.elements if e.page == 2][0]
            self.assertEqual(page2.status, "needs_review")      # unreviewed page stays unservable

    def test_patch_must_match_exactly_once(self):
        with self.assertRaises(ReviewError):
            apply_page_review("abc abc", {"decision": "approved", "page": 1, "patches": [{"find": "abc", "replace": "x"}]})
        with self.assertRaises(ReviewError):
            apply_page_review("abc", {"decision": "approved", "page": 1, "patches": [{"find": "zzz", "replace": "x"}]})

    def test_rejected_review_removes_page(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            review = {"doc_id": "g-guest", "page": 2, "decision": "rejected", "reviewer": "agent"}
            doc = load_document(write(tmp, "a.md", OCR_DOC), tmp, {}, make_lookup([review]))
            self.assertFalse([e for e in doc.elements if e.page == 2])

    def test_review_of_other_source_bytes_is_void(self):
        lookup = make_lookup([{"doc_id": "d", "page": 1, "decision": "approved", "reviewer": "a", "source_sha256": "AAA"}])
        self.assertIsNone(lookup("d", 1, "BBB"))
        self.assertIsNotNone(lookup("d", 1, "AAA"))

    def test_split_pages(self):
        pages = split_pages("intro\n<!-- page: 1 -->\nA\n<!-- page: 2 -->\nB")
        self.assertEqual([p for p, _ in pages], [-1, 1, 2])


if __name__ == "__main__":
    unittest.main()
