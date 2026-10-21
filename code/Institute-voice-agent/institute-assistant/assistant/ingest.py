"""
Builds (or rebuilds) the searchable vector index from every document under KB_DIR.

Run via: python build_index.py  (thin wrapper at project root)

Refreshes the configured collection using stable IDs. Existing data is retained until
extraction and embedding succeed; other collections are preserved.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from assistant.config import settings
from assistant.extract import extract_document
from assistant.telemetry import chroma_settings


def discover_files(kb_dir: Path) -> list[tuple[Path, str]]:
    """Use the first subfolder as category even for nested source directories."""
    files = []
    for path in sorted(kb_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".pdf", ".txt"):
            relative = path.relative_to(kb_dir)
            category = relative.parts[0] if len(relative.parts) > 1 else "general"
            if category not in settings.CATEGORIES:
                raise ValueError(f"Unknown knowledge base category: {category}")
            files.append((path, category))
    return files


def build_documents(kb_dir: Path) -> list[Document]:
    files = discover_files(kb_dir)
    if not files:
        print(f"⚠️  No .pdf or .txt files found under {kb_dir}/ — nothing to index yet.")
        return []

    documents = []
    for path, category in files:
        print(f"Extracting: {path} (category={category})")
        pages = extract_document(path, category)
        for p in pages:
            documents.append(Document(
                page_content=p.text,
                metadata={
                    "source_file": path.relative_to(kb_dir).as_posix(),
                    "category": p.category,
                    "page_number": p.page_number if p.page_number is not None else -1,
                },
            ))
        print(f"  -> {len(pages)} page(s)/section(s) extracted")
    return documents


def chunk_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def build_index():
    """Upsert stable chunk IDs, removing obsolete chunks only after all new writes succeed.

    Stop query processes during rebuilds and restart afterwards to clear cached retrieval.
    Unrelated collections and the old index survive extraction/embedding failures.
    """
    kb_dir = Path(settings.KB_DIR)
    persist_dir = Path(settings.CHROMA_PERSIST_DIR)

    documents = build_documents(kb_dir)
    if not documents:
        raise ValueError("No usable documents found. Existing index was preserved.")

    chunks = chunk_documents(documents)
    print(f"\nTotal chunks to index: {len(chunks)}")

    print(f"Loading embedding model ({settings.EMBEDDING_MODEL})... first run downloads it, cached after.")
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)

    print(f"Building index at {persist_dir}/ ...")
    store = Chroma(
        embedding_function=embeddings,
        collection_name=settings.CHROMA_COLLECTION_NAME,
        persist_directory=str(persist_dir),
        client_settings=chroma_settings(),
    )
    profile = (store._collection.metadata or {}).get("embedding_model")
    if profile and profile != settings.EMBEDDING_MODEL:
        raise ValueError("Embedding model changed. Build into a new CHROMA_COLLECTION_NAME.")
    if not profile and store._collection.count() and settings.EMBEDDING_MODEL != "sentence-transformers/all-MiniLM-L6-v2":
        raise ValueError("Legacy index has no model metadata. Build into a new collection for a different model.")
    ids = [hashlib.sha256((str(c.metadata) + c.page_content).encode()).hexdigest() for c in chunks]
    unique = dict(zip(ids, chunks))
    ids, chunks = list(unique), list(unique.values())
    vectors = embeddings.embed_documents([c.page_content for c in chunks])
    old_ids = set(store.get(include=[])['ids'])
    # Chroma's documented batch limit can be smaller than the corpus.
    batch_size = store._client.get_max_batch_size()
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        store._collection.upsert(ids=ids[start:start + batch_size],
                                 documents=[c.page_content for c in batch],
                                 metadatas=[c.metadata for c in batch],
                                 embeddings=vectors[start:start + batch_size])
    stale = list(old_ids - set(ids))
    for start in range(0, len(stale), batch_size):
        store.delete(ids=stale[start:start + batch_size])
    store._collection.modify(metadata={**(store._collection.metadata or {}), "embedding_model": settings.EMBEDDING_MODEL})
    print(f"\n✅ Index built successfully: {len(chunks)} chunks from {len(documents)} page(s)/section(s) "
          f"across {len(discover_files(kb_dir))} file(s).")
