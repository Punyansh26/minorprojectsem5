"""Keep graph tests away from installed releases, persistent caches and user checkpoints."""
from dataclasses import replace

import pytest

from assistant import nodes, llm


@pytest.fixture(autouse=True)
def isolated_graph_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(llm.settings, LLM_PROVIDER="groq"))
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings,
        LLM_PROVIDER="groq",
        KB_STATE_DIR=str(tmp_path / "kb_state"),
        RAG_CACHE_DB_PATH=str(tmp_path / "rag_cache.sqlite"), HISTORY_TURNS=10))
