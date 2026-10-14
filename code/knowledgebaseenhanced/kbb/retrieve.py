"""Evidence retrieval for the standalone kbb CLI/bot, served from the active immutable release.

Retrieval logic lives in ``kbb.release.ReleaseSearch`` (policy -> exact cutoff -> matched facts -> hybrid).  This
module only adapts its hits to the ``RetrievedEvidence`` shape used by ``kbb.bot``.  The previous
``KnowledgeRetriever`` read an unvetted index with hand-written facts and an unfiltered ``LIMIT 5`` cutoff
fallback; it was removed together with that index.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Config
from .store import read_json


class RetrievedEvidence:
    """Grounding block returned to the answering model."""

    def __init__(self, parent_id: str, title: str, heading_path: list[str], page_start: int, page_end: int, text: str,
                 score: float, source_file: str = "", status: str = "extracted", meta: dict[str, Any] | None = None):
        self.parent_id = parent_id
        self.title = title
        self.heading_path = heading_path
        self.page_start = page_start
        self.page_end = page_end
        self.text = text
        self.score = score
        self.source_file = source_file
        self.status = status
        self.meta = meta or {}

    def citation(self, cite_idx: int) -> str:
        loc = f"p. {self.page_start}" if self.page_start > 0 else "web"
        header = " › ".join(self.heading_path) if self.heading_path else self.title
        return f"[S{cite_idx}] {header} ({loc})\n{self.text}"


def active_release_root(cfg: Config) -> Path:
    """Directory of the release named by ``data/kbb/serving/active.json``."""
    pointer = read_json(cfg.work / "serving" / "active.json")
    if not pointer:
        raise FileNotFoundError(f"No active release in {cfg.work / 'serving'}; run build-release, evaluate and activate.")
    return cfg.work / "serving" / "releases" / pointer["release"]


class ReleaseRetriever:
    """Same ``search(question, top_k)`` contract the bot already used."""

    def __init__(self, cfg: Config, release_root: Path, device: str = "cpu"):
        from .release import ReleaseSearch
        self.cfg, self.root = cfg, release_root
        self.engine = ReleaseSearch(release_root, device=device)

    def search(self, question: str, top_k: int = 5) -> list[RetrievedEvidence]:
        out = []
        for hit in self.engine.search(question, top_k):
            block = self.engine.parents.get(hit.block_id, {})
            out.append(RetrievedEvidence(
                parent_id=hit.block_id, title=hit.title, heading_path=block.get("heading_path", []),
                page_start=hit.page_number, page_end=hit.page_number, text=hit.text, score=hit.score,
                source_file=hit.source_file, status=block.get("verification_status", "extracted"), meta=block))
        return out
