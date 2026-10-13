"""Canonical document storage manager.

Stores extracted and verified documents in a clean, high-performance format:
Each document lives in `work/docs/<doc_id>/`:
  1. `meta.json`: Full document metadata, SHA-256, format, timestamps.
  2. `elements.jsonl` (or `elements.jsonl.gz`): High-efficiency streaming format
     containing structured `Element`s with bounding boxes, types, and tables.
  3. `document.md`: Page-anchored Markdown view (`<!-- page: N -->`) for human inspection
     and LLM prompts.
  4. `pages.json`: Per-page stats, triage routing, and verification status.
  5. `second_reads.jsonl`: Independent second reads for fidelity auditing.
"""
from __future__ import annotations

import gzip
import logging
from pathlib import Path
from typing import Any

import orjson

from .config import Config
from .models import Element, PageInfo, SecondRead
from .store import read_json, read_jsonl, write_json, write_jsonl, write_text

log = logging.getLogger(__name__)


class CanonicalDoc:
    """In-memory wrapper around a canonical document's artifacts."""

    def __init__(self, doc_dir: Path):
        self.doc_dir = doc_dir
        self.meta: dict[str, Any] = read_json(doc_dir / "meta.json", {})
        self.pages: list[PageInfo] = [PageInfo(**p) for p in read_json(doc_dir / "pages.json", [])]
        self._elements: list[Element] | None = None
        self._second_reads: list[SecondRead] | None = None

    @property
    def elements(self) -> list[Element]:
        if self._elements is None:
            self._elements = self.load_elements()
        return self._elements

    @property
    def second_reads(self) -> list[SecondRead]:
        if self._second_reads is None:
            self._second_reads = self.load_second_reads()
        return self._second_reads

    def load_elements(self) -> list[Element]:
        gz_path = self.doc_dir / "elements.jsonl.gz"
        jsonl_path = self.doc_dir / "elements.jsonl"
        items = []

        if gz_path.exists():
            with gzip.open(gz_path, "rb") as fh:
                for line in fh:
                    if line.strip():
                        items.append(Element.from_dict(orjson.loads(line)))
        elif jsonl_path.exists():
            for d in read_jsonl(jsonl_path):
                items.append(Element.from_dict(d))
        return items

    def load_second_reads(self) -> list[SecondRead]:
        sr_path = self.doc_dir / "second_reads.jsonl"
        if not sr_path.exists():
            return []
        return [SecondRead.from_dict(d) for d in read_jsonl(sr_path)]

    def markdown(self) -> str:
        md_path = self.doc_dir / "document.md"
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
        return ""


def save_canonical_doc(
    cfg: Config,
    doc_id: str,
    meta: dict[str, Any],
    elements: list[Element],
    pages: list[PageInfo],
    second_reads: list[SecondRead] | None = None,
) -> CanonicalDoc:
    """Persist extraction results into the canonical storage layout."""
    doc_dir = cfg.doc_dir(doc_id)
    doc_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write metadata
    write_json(doc_dir / "meta.json", meta)

    # 2. Write pages info
    write_json(doc_dir / "pages.json", [p.__dict__ for p in pages])

    # 3. Write elements as streaming JSONL or GZ
    raw_dicts = [el.to_dict() for el in elements]
    jsonl_path = doc_dir / "elements.jsonl"
    write_jsonl(jsonl_path, raw_dicts)

    # Compress if it exceeds configured threshold
    threshold_bytes = cfg.storage.gzip_elements_over_kb * 1024
    if jsonl_path.stat().st_size > threshold_bytes:
        gz_path = doc_dir / "elements.jsonl.gz"
        with jsonl_path.open("rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
            f_out.writelines(f_in)
        jsonl_path.unlink()

    # 4. Write second reads if present
    if second_reads and cfg.storage.keep_second_reads:
        write_jsonl(doc_dir / "second_reads.jsonl", [sr.to_dict() for sr in second_reads])

    # 5. Generate and write page-anchored Markdown view
    if cfg.storage.write_markdown_view:
        md_text = render_document_markdown(meta, elements)
        write_text(doc_dir / "document.md", md_text)

    return CanonicalDoc(doc_dir)


def render_document_markdown(meta: dict[str, Any], elements: list[Element]) -> str:
    """Render a clean, page-anchored Markdown document from canonical elements."""
    lines: list[str] = []

    # Front-matter
    lines.append("---")
    for k in ("doc_id", "title", "category", "topic", "years", "period", "source_file", "source_sha256"):
        if k in meta and meta[k]:
            val = meta[k]
            lines.append(f"{k}: {val}")
    lines.append("---")
    lines.append("")

    title = meta.get("title") or "Document"
    lines.append(f"# {title}\n")

    current_page = None
    for el in elements:
        # Add page anchors
        if el.page is not None and el.page > 0 and el.page != current_page:
            current_page = el.page
            lines.append(f"\n<!-- page: {current_page} -->\n")

        # Element rendering
        if el.type == "heading":
            level = max(1, min(6, el.level or 2))
            lines.append(f"{'#' * level} {el.text}\n")
        elif el.type == "table":
            from .tables import render_markdown
            lines.append(f"<!-- table: {el.id} -->")
            if el.table:
                if el.table.caption:
                    lines.append(f"**Table: {el.table.caption}**\n")
                lines.append(render_markdown(el.table))
            else:
                lines.append(el.text)
            lines.append("")
        elif el.type == "list_item":
            lines.append(f"- {el.text}")
        elif el.type == "code":
            lines.append(f"```\n{el.text}\n```\n")
        elif el.type == "kv":
            lines.append(f"**{el.text}**\n")
        elif el.type == "figure":
            lines.append(f"> **[Figure]** {el.text}\n")
        else:
            # Paragraph
            lines.append(f"{el.text}\n")

    return "\n".join(lines)


def load_canonical_doc(cfg: Config, doc_id: str) -> CanonicalDoc:
    """Load an existing canonical document."""
    doc_dir = cfg.doc_dir(doc_id)
    if not (doc_dir / "meta.json").exists():
        raise FileNotFoundError(f"Canonical document not found: {doc_dir}")
    return CanonicalDoc(doc_dir)
