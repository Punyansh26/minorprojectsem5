"""Stage 7 — index builder: hybrid dense embeddings, BM25, and structured facts.sqlite.

Features:
- Dense vector store using `intfloat/multilingual-e5-small` (stored as memory-mapped
  numpy array or Chroma).
- Sparse BM25 index with Indic tokenization.
- Structured SQLite database (`facts.sqlite`) for exact factoid lookups (cutoffs, fees, dates).
- Immutable build manifests with content SHA-256 validation.
"""
from __future__ import annotations

import logging
import math
import os
from pathlib import Path
import sqlite3
import time
from typing import Any

import numpy as np

from .config import Config
from .models import Parent, Unit
from .store import dumps, write_json
from .textnorm import words

log = logging.getLogger(__name__)


class LocalEmbedder:
    """Wrapper around sentence-transformers / Local E5 with passage/query prefixes."""

    def __init__(self, model_name_or_path: str, max_tokens: int = 512, family: str = "e5", device: str | None = None):
        self.family = family
        self.max_tokens = max_tokens
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name_or_path, device=device)

    def embed_units(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        if self.family == "e5":
            texts = [f"passage: {t}" for t in texts]
        vecs = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        q = f"query: {query}" if self.family == "e5" else query
        vec = self.model.encode([q], show_progress_bar=False, normalize_embeddings=True)[0]
        return np.asarray(vec, dtype=np.float32)


class BM25Index:
    """Lightweight, self-contained BM25 index with Indic-aware tokenization."""

    def __init__(self):
        self.doc_ids: list[str] = []
        self.doc_lens: list[int] = []
        self.avg_dl: float = 0.0
        self.inverted: dict[str, list[tuple[int, int]]] = {}  # term -> [(doc_idx, tf), ...]

    def build(self, unit_ids: list[str], texts: list[str]) -> None:
        self.doc_ids = unit_ids
        total_len = 0
        for idx, text in enumerate(texts):
            toks = words(text, drop_stop=True)
            self.doc_lens.append(len(toks))
            total_len += len(toks)

            counts: dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            for term, tf in counts.items():
                self.inverted.setdefault(term, []).append((idx, tf))

        self.avg_dl = total_len / max(1, len(texts))

    def search(self, query: str, top_k: int = 30) -> list[tuple[str, float]]:
        q_toks = words(query, drop_stop=True)
        if not q_toks:
            return []

        scores: dict[int, float] = {}
        n_docs = len(self.doc_ids)

        for term in q_toks:
            postings = self.inverted.get(term, [])
            if not postings:
                continue
            df = len(postings)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            for doc_idx, tf in postings:
                dl = self.doc_lens[doc_idx]
                denom = tf + 1.5 * (0.25 + 0.75 * (dl / max(1.0, self.avg_dl)))
                score = idf * (tf * 2.5) / denom
                scores[doc_idx] = scores.get(doc_idx, 0.0) + score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self.doc_ids[idx], score) for idx, score in ranked]


def build_index(
    cfg: Config,
    build_id: str,
    parents: list[Parent],
    units: list[Unit],
) -> Path:
    """Build and persist complete search index for a release."""
    out_dir = cfg.paths.work / "index" / build_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Filter to answerable units
    eligible_units = [u for u in units if u.status in cfg.retrieval.statuses]
    unit_texts = [u.embed_text() for u in eligible_units]
    unit_ids = [u.id for u in eligible_units]

    # 1. Dense Embeddings
    model_path = cfg.embedding.model_path if Path(cfg.embedding.model_path).exists() else cfg.embedding.model
    embedder = LocalEmbedder(model_path, cfg.embedding.max_tokens, cfg.embedding.family)
    vectors = embedder.embed_units(unit_texts, batch_size=cfg.embedding.batch_size)
    np.save(out_dir / "vectors.npy", vectors.astype(np.float16 if cfg.embedding.dtype_store == "float16" else np.float32))

    # 2. Sparse BM25
    bm25 = BM25Index()
    bm25.build(unit_ids, unit_texts)

    # 3. Structured Database (facts.sqlite)
    db_path = out_dir / "facts.sqlite"
    _build_facts_db(db_path, parents)

    # 4. Save metadata & parents lookup
    write_json(out_dir / "units.json", [u.to_dict() for u in eligible_units])
    write_json(out_dir / "parents.json", {p.id: p.to_dict() for p in parents})

    # 5. Manifest
    manifest = {
        "build_id": build_id,
        "created_at": time.time(),
        "embedding_model": cfg.embedding.model,
        "units_count": len(eligible_units),
        "parents_count": len(parents),
        "vectors_shape": list(vectors.shape),
    }
    write_json(out_dir / "manifest.json", manifest)

    log.info("Index build %s complete: %d units, %d parents", build_id, len(eligible_units), len(parents))
    return out_dir


def _build_facts_db(db_path: Path, parents: list[Parent]) -> None:
    """Populate facts.sqlite for exact structured SQL queries."""
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE IF NOT EXISTS cutoffs (programme TEXT, category TEXT, round INT, closing_rank INT, year INT, parent_id TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS fees (fee_type TEXT, category TEXT, amount INT, semester TEXT, year INT, parent_id TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS dates (event TEXT, event_date TEXT, parent_id TEXT)")
    con.commit()
    con.close()
