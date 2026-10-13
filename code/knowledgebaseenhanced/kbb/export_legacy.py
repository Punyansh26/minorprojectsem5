"""Stage 9 — export adapter to legacy `institute-assistant` schema.

Converts verified parents and units into the block/parent schema expected by
`code/Institute-voice-agent/institute-assistant/assistant/kb/`:
- `make_block()` fields: id, source_id, source_file, title, category, topic,
  page_number, kind, text, source_sha256, years, period, programme,
  verification_status, extraction_method.
- Extra enriched fields: `heading_path`, `context`, `questions`.
- Enables drop-in consumption by `kb_pipeline.py build -> evaluate -> activate`.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config import Config
from .models import Parent
from .store import read_json, write_json

log = logging.getLogger(__name__)


def export_to_legacy_blocks(
    cfg: Config,
    parents: list[Parent],
    out_dir: Path,
) -> dict[str, Any]:
    """Convert parents into legacy `blocks.json` format."""
    out_dir.mkdir(parents=True, exist_ok=True)
    blocks: list[dict[str, Any]] = []

    for p in parents:
        meta = p.meta
        block = {
            "id": p.id,
            "source_id": meta.get("doc_id", p.doc_id),
            "source_file": meta.get("source_file", meta.get("title", "")),
            "source_url": meta.get("source_url", ""),
            "title": meta.get("title", ""),
            "category": meta.get("category", "general"),
            "topic": meta.get("topic", "general"),
            "page_number": p.page_start,
            "kind": p.kind,
            "text": p.text,
            "source_sha256": meta.get("source_sha256", ""),
            "years": meta.get("years", []),
            "period": meta.get("period", ""),
            "programme": meta.get("programme", ""),
            "published_at": meta.get("published_at", ""),
            "historical": meta.get("historical", False),
            "verification_status": p.status,
            "extraction_method": p.readers[0] if p.readers else "docling",
            "heading_path": p.heading_path,
            "context": p.context,
            "questions": p.questions,
            "related_evidence_block_ids": p.related_parent_ids,
        }
        blocks.append(block)

    write_json(out_dir / "blocks.json", blocks)

    # Also emit parents dictionary
    parents_dict = {b["id"]: b for b in blocks}
    write_json(out_dir / "parents.json", parents_dict)

    summary = {
        "blocks_count": len(blocks),
        "answerable_blocks": sum(b["verification_status"] in {"extracted", "approved", "machine_verified"} for b in blocks),
        "pending_blocks": sum(b["verification_status"] == "needs_review" for b in blocks),
    }
    write_json(out_dir / "export_summary.json", summary)
    log.info("Exported %d legacy blocks to %s", len(blocks), out_dir)
    return summary
