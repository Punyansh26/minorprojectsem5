"""Combine semantic and keyword search while preserving inspectable source metadata."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from assistant.config import settings


@dataclass
class RetrievedChunk:
    text: str
    source_file: str
    category: str
    page_number: int
    score: float  # Chroma distance when available; -1 for lexical-only matches.
    source_url: str = ""
    title: str = ""
    period: str = ""
    years: str = ""
    block_id: str = ""
    kind: str = "text"
    extraction_method: str = "native"
    asset: str = ""
    historical: bool = False
    verified: bool = False
    source_sha256: str = ""
    audience: str = ""
    conflict_note: str = ""
    scope_note: str = ""
    source_owner: str = ""
    review_by: str = ""
    source_status: str = ""
    superseded_by: str = ""


_EMBEDDINGS = None
_VECTORSTORE = None
_LEXICAL_CACHE = None
_RELEASE_ENGINE = None
_AUTO_RELEASE = object()


def get_release_engine(release=_AUTO_RELEASE):
    """Follow the atomic release pointer and clear model/lexical caches on changes."""
    global _RELEASE_ENGINE
    from assistant.kb.common import active_release
    from assistant.kb.search import SearchEngine
    active = active_release(Path(settings.KB_STATE_DIR)) if release is _AUTO_RELEASE else release
    if not active:
        return None
    root, manifest = active
    if _RELEASE_ENGINE is None or _RELEASE_ENGINE.root != root:
        if manifest.get("engine") == "kbb":
            # kbb releases verify their own content hashes when loaded.
            from assistant.kb.kbb_engine import KbbSearchEngine
            _RELEASE_ENGINE = KbbSearchEngine(root, manifest)
            return _RELEASE_ENGINE
        if manifest.get("manifest_version",1) >= 2:
            from assistant.kb.integrity import verify
            verify(root,manifest)
        _RELEASE_ENGINE = SearchEngine(root, manifest)
    return _RELEASE_ENGINE
_STOPWORDS = set("a an the is are was were be been of to in on for from and or at by with what how when where which who can could would should do does did me my i you your please about tell it this that there have has iiit naya raipur institute college".split())


def source_years(source_file: str) -> set[int]:
    """Read explicit document years from filenames, including ranges such as 2022_23."""
    years = {int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", source_file)}
    for start, end in re.findall(r"(20\d{2})[_-](\d{2})(?!\d)", source_file):
        years.update(range(int(start), int(start[:2] + end) + 1))
    return years


def query_years(question: str) -> set[int]:
    """Extract explicit years from the question. When none are mentioned, return empty
    to allow all documents through — the generate node handles year preference itself."""
    return {int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", question)}


def source_matches_year(source_file: str, question: str) -> bool:
    """Keep undated sources; when no year in query, allow all documents through."""
    src = source_years(source_file)
    qry = query_years(question)
    if not qry:
        return True  # No year constraint from the query — allow everything.
    return not src or bool(src & qry)


def _get_embeddings():
    global _EMBEDDINGS
    if _EMBEDDINGS is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _EMBEDDINGS = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
    return _EMBEDDINGS


def _get_vectorstore():
    global _VECTORSTORE
    if _VECTORSTORE is None:
        from langchain_chroma import Chroma
        from assistant.telemetry import chroma_settings
        _VECTORSTORE = Chroma(
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=_get_embeddings(),
            persist_directory=settings.CHROMA_PERSIST_DIR,
            client_settings=chroma_settings(), create_collection_if_not_exists=False,
        )
        profile = (_VECTORSTORE._collection.metadata or {}).get("embedding_model")
        if profile and profile != settings.EMBEDDING_MODEL:
            _VECTORSTORE = None
            raise ValueError("Index embedding model differs from EMBEDDING_MODEL; rebuild the index.")
    return _VECTORSTORE


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Share the configured embedding model with knowledge gap analysis."""
    engine = get_release_engine()
    return engine.embeddings.embed_questions(texts) if engine else _get_embeddings().embed_documents(texts)


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.casefold()) if t not in _STOPWORDS and len(t) > 1]


def _lexical_rank(store, question: str, category: str | None, limit: int):
    global _LEXICAL_CACHE
    if _LEXICAL_CACHE is None or _LEXICAL_CACHE[0] is not store:
        data = store.get(include=["documents", "metadatas"])
        rows = []
        for text, metadata in zip(data["documents"], data["metadatas"]):
            metadata = metadata or {}
            if text:
                rows.append((text, metadata, Counter(_tokens(text))))
        frequency = Counter(term for _, _, terms in rows for term in terms)
        average = sum(sum(terms.values()) for _, _, terms in rows) / max(1, len(rows))
        _LEXICAL_CACHE = (store, rows, frequency, average)
    _, rows, frequency, average = _LEXICAL_CACHE
    query_terms = set(_tokens(question))
    ranked = []
    for text, metadata, counts in rows:
        if category and metadata.get("category") != category:
            continue
        if not source_matches_year(metadata.get("source_file", ""), question):
            continue
        score = 0.0
        length = sum(counts.values())
        for term in query_terms:
            count = counts[term]
            if count:
                idf = math.log(1 + (len(rows) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                score += idf * count * 2.5 / (count + 1.5 * (0.25 + 0.75 * length / max(average, 1)))
        if score > 0:
            ranked.append((text, metadata, score))
    return sorted(ranked, key=lambda row: row[2], reverse=True)[:limit]


def retrieve(question: str, k: int | None = None, category: str | None = None,
             preferred_category: str | None = None, filters: dict | None = None,
             *, release=_AUTO_RELEASE) -> list[RetrievedChunk]:
    """Fuse ranks, deduplicate passages, and prefer a topic without hiding other categories.

    category is an explicit hard filter for the retrieval debugging CLI. The agent uses
    preferred_category instead. A distance cutoff only gates the semantic candidates;
    exact keyword matches can still be useful, and generation must verify answerability.
    Omit release to follow the active pointer; pass its (root, manifest) snapshot to pin
    a turn, or None to explicitly use the legacy index without re-reading the pointer.
    """
    if not question.strip():
        return []
    k = settings.TOP_K if k is None else k
    if k < 1:
        raise ValueError("k must be positive")
    engine = get_release_engine() if release is _AUTO_RELEASE else get_release_engine(release)
    if engine:
        return engine.search(question, k, category, preferred_category, filters)
    if not Path(settings.CHROMA_PERSIST_DIR, "chroma.sqlite3").exists() and _VECTORSTORE is None:
        return []
    store = _get_vectorstore()
    limit = max(k, settings.RETRIEVAL_FETCH_K)
    semantic = store.similarity_search_with_score(question, k=limit, filter={"category": category} if category else None)
    candidates = {}

    def add(text, metadata, rank, distance, weight):
        if not source_matches_year(metadata.get("source_file", ""), question):
            return
        key = " ".join(text.casefold().split())
        if not key:
            return
        if key not in candidates:
            candidates[key] = [text, metadata, distance, 0.0]
        candidates[key][3] += weight / (60 + rank)

    for rank, (doc, distance) in enumerate(semantic, 1):
        if math.isfinite(distance) and distance <= settings.RETRIEVAL_MAX_DISTANCE:
            add(doc.page_content, doc.metadata, rank, float(distance), 1.0)
    for rank, (text, metadata, _) in enumerate(_lexical_rank(store, question, category, limit), 1):
        add(text, metadata, rank, -1.0, 1.0)
    ranked = sorted(candidates.values(),
                    key=lambda row: row[3]
                    * (1.1 if preferred_category and row[1].get("category") == preferred_category else 1)
                    * (2.0 if source_years(row[1].get("source_file", "")) & query_years(question) else 1),
                    reverse=True)
    return [RetrievedChunk(text, str(meta.get("source_file", "unknown")), str(meta.get("category", "general")),
                           int(meta.get("page_number", -1)), distance)
            for text, meta, distance, _ in ranked[:k]]
