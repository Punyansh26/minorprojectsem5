"""
Extracts clean text from source documents (PDFs and plain .txt files) in the knowledge base.
Unchanged logic from the original kb-pipeline project — see ingest.py for how this is used.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass
class ExtractedPage:
    text: str
    source_file: str
    category: str
    page_number: int | None


def extract_pdf(path: Path, category: str) -> list[ExtractedPage]:
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(ExtractedPage(text=text, source_file=path.name, category=category, page_number=i))
    return pages


def extract_txt(path: Path, category: str) -> list[ExtractedPage]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    return [ExtractedPage(text=text, source_file=path.name, category=category, page_number=None)]


def extract_document(path: Path, category: str) -> list[ExtractedPage]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path, category)
    elif suffix == ".txt":
        return extract_txt(path, category)
    else:
        raise ValueError(f"Unsupported file type: {path} (only .pdf and .txt are supported)")
