"""Verify ranking and actual Chroma integration with local deterministic embeddings."""
from dataclasses import replace
from unittest.mock import Mock

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from assistant import retrieval
from assistant.telemetry import chroma_settings


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(retrieval, "_LEXICAL_CACHE", None)
    monkeypatch.setattr(retrieval, "_VECTORSTORE", None)
    monkeypatch.setattr(retrieval, "settings", replace(retrieval.settings, KB_STATE_DIR=str(tmp_path / "kb_state")))


def test_hybrid_search_keeps_cross_category_exact_match_and_deduplicates(monkeypatch):
    doc = Document(page_content="Hostel deposit refund requires the clearance form.", metadata={"category": "general", "source_file": "faq.txt", "page_number": 1})
    noise = Document(page_content="Annual report about sports awards.", metadata={"category": "hostel"})
    store = Mock()
    store.similarity_search_with_score.return_value = [(noise, 4.0), (doc, 0.3), (doc, 0.4)]
    store.get.return_value = {"documents": [doc.page_content, noise.page_content], "metadatas": [doc.metadata, noise.metadata]}
    monkeypatch.setattr(retrieval, "_VECTORSTORE", store)
    chunks = retrieval.retrieve("hostel deposit refund", preferred_category="hostel")
    assert len(chunks) == 1
    assert chunks[0].source_file == "faq.txt"
    assert store.similarity_search_with_score.call_args.kwargs["filter"] is None


def test_no_index_returns_empty_without_loading_embeddings(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "settings", replace(retrieval.settings, CHROMA_PERSIST_DIR=str(tmp_path)))
    get = Mock(side_effect=AssertionError("Model should not load"))
    monkeypatch.setattr(retrieval, "_get_embeddings", get)
    assert retrieval.retrieve("admission fees") == []
    get.assert_not_called()


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        return [float("hostel" in text.lower()), float("admission" in text.lower()), 0.1]


def test_real_chroma_telemetry_query_and_metadata(tmp_path, monkeypatch, caplog):
    from langchain_chroma import Chroma
    store = Chroma(collection_name="test_helpdesk", persist_directory=str(tmp_path),
                   embedding_function=LocalEmbeddings(), client_settings=chroma_settings())
    store.add_documents([Document(page_content="Hostel applications need a signed form.",
                                 metadata={"source_file": "hostel/form.txt", "category": "hostel", "page_number": 3})])
    monkeypatch.setattr(retrieval, "_VECTORSTORE", store)
    chunks = retrieval.retrieve("hostel application")
    assert chunks[0].page_number == 3
    assert "Failed to send telemetry" not in caplog.text
    store.delete_collection()


def test_document_year_selection():
    assert retrieval.source_years("AR_2022_23.pdf") == {2022, 2023}
    assert not retrieval.source_matches_year("AR_2022_23.pdf", "Admission in 2026")
    assert retrieval.source_matches_year("AR_2022_23.pdf", "Admission in 2023")
    assert retrieval.source_matches_year("BTECH_2026.pdf", "Admission in 2026")
    assert retrieval.source_matches_year("FAQ.pdf", "hostel facilities")


def test_new_release_supersedes_cached_legacy_store(monkeypatch):
    old = Mock()
    engine = Mock()
    engine.search.return_value = ["verified release evidence"]
    monkeypatch.setattr(retrieval, "_VECTORSTORE", old)
    monkeypatch.setattr(retrieval, "get_release_engine", lambda: engine)
    assert retrieval.retrieve("admission fees") == ["verified release evidence"]
    old.similarity_search_with_score.assert_not_called()
