"""Check rebuild preservation and stable IDs using a temporary real Chroma collection."""
from dataclasses import replace

import pytest
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from assistant import ingest
from assistant.telemetry import chroma_settings


class LocalEmbeddings(Embeddings):
    def __init__(self, **kwargs):
        pass

    def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]

    def embed_query(self, text):
        return [0.1, 0.2]


def test_rebuild_idempotent_removes_stale_and_preserves_other_collections(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    source_dir = kb / "admissions" / "2026"
    source_dir.mkdir(parents=True)
    source = source_dir / "reporting.txt"
    source.write_text("Bring the signed application form for admission reporting.")
    settings = replace(ingest.settings, KB_DIR=str(kb), CHROMA_PERSIST_DIR=str(tmp_path / "index"))
    monkeypatch.setattr(ingest, "settings", settings)
    monkeypatch.setattr(ingest, "HuggingFaceEmbeddings", LocalEmbeddings)
    other = Chroma(collection_name="unrelated", persist_directory=settings.CHROMA_PERSIST_DIR,
                   client_settings=chroma_settings(), embedding_function=LocalEmbeddings())
    other.add_documents([Document(page_content="Keep this unrelated collection.")])
    ingest.build_index()
    store = Chroma(collection_name=settings.CHROMA_COLLECTION_NAME, persist_directory=settings.CHROMA_PERSIST_DIR,
                   client_settings=chroma_settings(), embedding_function=LocalEmbeddings())
    first = store.get()
    assert first["metadatas"][0]["category"] == "admissions"
    assert first["metadatas"][0]["source_file"] == "admissions/2026/reporting.txt"
    ingest.build_index()
    assert store.get()["ids"] == first["ids"]
    source.write_text("Bring the updated reporting form.")
    ingest.build_index()
    assert store.get()["documents"] == ["Bring the updated reporting form."]
    assert other._collection.count() == 1

    def broken_embed(self, texts):
        raise RuntimeError("embedding failed")
    source.write_text("This update cannot be embedded.")
    monkeypatch.setattr(LocalEmbeddings, "embed_documents", broken_embed)
    with pytest.raises(RuntimeError, match="embedding failed"):
        ingest.build_index()
    assert store.get()["documents"] == ["Bring the updated reporting form."]
    store.delete_collection()
    other.delete_collection()
