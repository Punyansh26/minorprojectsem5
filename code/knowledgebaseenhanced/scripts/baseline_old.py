#!/usr/bin/env python3
"""Freeze what the legacy institute-assistant release answers today.

Runs every reviewed legacy evaluation case against the *active legacy release* (read-only) and
writes ``eval/baseline_old.json``.  The new knowledge base must not do worse than this file on any
case the legacy store answered correctly.  Runs on CPU so it never competes with MMS/Ollama.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT.parent / "Institute-voice-agent" / "institute-assistant"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LEGACY))
os.environ["KB_STATE_DIR"] = str(LEGACY / "kb_state")


def main() -> None:
    from assistant.kb.common import active_release
    from assistant.kb.search import SearchEngine
    from assistant.config import settings
    from kbb.audit import baseline_from_legacy

    root, manifest = active_release(Path(settings.KB_STATE_DIR))
    engine = SearchEngine(root, manifest)
    engine.embeddings.embed_query("warmup")
    summary = baseline_from_legacy(
        LEGACY / "kb_state", LEGACY / "docs" / "kb_evaluation_cases.json",
        ROOT / "eval" / "baseline_old.json", search=lambda q: engine.search(q, 6))
    print({k: v for k, v in summary.items() if k != "rows"}, "release", manifest["release"])


if __name__ == "__main__":
    main()
