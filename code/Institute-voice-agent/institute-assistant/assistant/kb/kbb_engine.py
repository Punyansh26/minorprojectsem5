"""Serve a ``kbb`` release through the interface the LangGraph nodes already use.

The retrieval, ranking, exact cutoff lookup, matched facts and policy binding all live in the ``kbb`` package
(``kbb.release.ReleaseSearch``); this adapter only loads it and converts hits to ``RetrievedChunk`` so graph,
grounding and citation code stay unchanged.  Selected when the active release manifest says ``engine: kbb``.
"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict
from pathlib import Path

_DEFAULT_KBB_ROOT = Path(__file__).resolve().parents[4] / "knowledgebaseenhanced"


def kbb_root() -> Path:
    return Path(os.getenv("KBB_ROOT", str(_DEFAULT_KBB_ROOT))).resolve()


def _import_release_search():
    root = str(kbb_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from kbb.release import ReleaseSearch
    return ReleaseSearch


class KbbSearchEngine:
    """Same ``search`` signature as ``assistant.kb.search.SearchEngine``."""

    def __init__(self, root: Path, manifest: dict):
        self.root, self.manifest = Path(root), manifest
        # Query embedding runs on CPU so it never competes with MMS/Ollama for the 8 GB GPU.
        self._engine = _import_release_search()(self.root, device=os.getenv("KBB_DEVICE", "cpu"))
        self.parents = self._engine.parents
        self.embeddings = self._engine.embeddings

    def search(self, question: str, k: int, category=None, preferred_category=None, filters=None):
        from assistant.retrieval import RetrievedChunk
        hits = self._engine.search(question, k, category, preferred_category, filters)
        return [RetrievedChunk(**asdict(hit)) for hit in hits]
