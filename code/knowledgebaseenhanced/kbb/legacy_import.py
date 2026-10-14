"""Migrate reviewed evidence and exact records from the previous (legacy) knowledge-base release.

Why migrate instead of re-deriving:
* The 611 JoSAA/CSAB rank rows were collected from the official counselling site and validated row by row;
  their evidence blocks are reused *verbatim* (same ids, same text, same source hash).
* Pages of the admission brochure and the academic calendar carry visually reviewed text
  (``kb_state/reviews.json``: rendered page compared with extraction).  That reviewed text replaces the OCR text.
* Government scheme pages (PM Vidyalaxmi, scholarship notices) exist only in the legacy store.

The legacy ``kb_state`` directory is only ever read.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import Parent, STATUS_RANK, weakest
from .store import read_json

OVERRIDE_SOURCES = {"B TECH_2026.pdf", "ACF2026.pdf"}          # reviewed text replaces new OCR/extraction
PAGE_EXTRA_FIELDS = ("audience", "conflict_note", "scope_note", "source_owner", "review_by", "source_status",
                     "superseded_by", "related_evidence_block_ids")


def active_legacy(state: Path) -> tuple[Path, dict[str, Any]]:
    pointer = read_json(state / "active.json")
    root = state / "releases" / pointer["release"]
    return root, read_json(root / "release.json")


def load_legacy(state: Path) -> dict[str, Any]:
    root, manifest = active_legacy(state)
    return {"root": root, "manifest": manifest,
            "parents": read_json(root / "parents.json"),
            "records": [r for r in read_json(state / "records.json", [])],
            "policies": read_json(root / "policies.json", {"rules": []}),
            "sources": read_json(root / "sources.json", {"sources": []}),
            "reviews": read_json(state / "reviews.json", {})}


def _as_markdown(block: dict) -> str:
    """Legacy tables are ``a | b`` lines; make them Markdown tables so row/column keys survive."""
    lines = block["text"].splitlines()
    if block.get("kind") != "table" or not lines:
        return block["text"]
    rows = [[c.strip() for c in ln.split(" | ")] for ln in lines if " | " in ln]
    if len(rows) < 2:
        return block["text"]
    width = max(len(r) for r in rows)
    out = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    out.insert(1, "| " + " | ".join("---" for _ in range(width)) + " |")
    return "\n".join(out)


def page_overrides(legacy: dict[str, Any]) -> tuple[dict[str, dict[int, dict]], dict[tuple[str, int], dict]]:
    """Reviewed page text for ``OVERRIDE_SOURCES`` plus the page-level metadata the old blocks carried."""
    pages: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for block in legacy["parents"].values():
        name = Path(block["source_file"]).name
        if name in OVERRIDE_SOURCES and block.get("kind") in {"text", "table"}:
            pages[name][int(block["page_number"])].append(block)
    overrides: dict[str, dict[int, dict]] = {}
    extras: dict[tuple[str, int], dict] = {}
    for name, by_page in pages.items():
        overrides[name] = {}
        for page, blocks in by_page.items():
            blocks.sort(key=lambda b: (b.get("bbox") or [0, 0])[1] if b.get("bbox") else 0)
            reviewer = next((b.get("reviewer") for b in blocks if b.get("reviewer")), "legacy extraction")
            status = weakest(b["verification_status"] for b in blocks)
            # Replace the new text only where a reviewer actually corrected it against the rendered page.
            # Pages whose review merely added metadata (e.g. p8's related-evidence links) keep the new,
            # more complete extraction and just inherit the metadata below.
            corrected = any((legacy["reviews"].get(b["id"]) or {}).get("text") for b in blocks)
            if corrected:
                overrides[name][page] = {"text": "\n\n".join(_as_markdown(b) for b in blocks), "status": status,
                                         "reader": "legacy-reviewed", "reviewer": reviewer}
            extra = {}
            for b in blocks:
                for key in PAGE_EXTRA_FIELDS:
                    if b.get(key):
                        extra[key] = b[key]
            if extra:
                extras[(name, page)] = extra
    return overrides, extras


def legacy_only_parents(legacy: dict[str, Any], new_basenames: set[str]) -> list[Parent]:
    """One evidence parent per legacy block for sources the new corpus does not contain."""
    parents = []
    for block in legacy["parents"].values():
        name = Path(block["source_file"]).name
        if name in new_basenames or name in OVERRIDE_SOURCES or block["id"].startswith("record-"):
            continue
        if block["source_file"].startswith("general/") and name.endswith(".pdf"):
            continue                                  # general PDFs are covered by the new corpus
        meta = {k: v for k, v in block.items() if k not in {"text", "rows", "bbox", "asset"}}
        meta.update(doc_id="legacy:" + block["source_id"], years=block.get("years", []), legacy_block=True)
        kind = "table" if block["kind"] in {"table", "cutoff"} else "text"
        parents.append(Parent(
            id=block["id"], doc_id=meta["doc_id"], kind=kind if block["kind"] != "cutoff" else "cutoff",
            text=block["text"], heading_path=[x for x in (block.get("title", ""), block.get("period", "")) if x], element_ids=[],
            page_start=int(block.get("page_number", -1)), page_end=int(block.get("page_number", -1)),
            status=block["verification_status"], readers=[block.get("extraction_method", "legacy")],
            critical=block["kind"] in {"cutoff", "finance", "scholarship"}, meta=meta,
            related_parent_ids=list(block.get("related_evidence_block_ids", []))))
    return parents


def sources_inventory(legacy: dict[str, Any]) -> dict[str, dict]:
    return {s["id"]: s for s in legacy["sources"].get("sources", [])}
