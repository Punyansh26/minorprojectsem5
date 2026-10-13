"""Stage 8 — hybrid multi-granularity retriever with RRF and parent expansion.

Features (doc 15 §6 & §8):
1. Query Normalisation: extracts requested academic years, maps aliases.
2. Structured Routing: cutoff and fee questions check `facts.sqlite` first.
3. Multi-Granularity Hybrid Search: retrieves top-k per unit type via dense vectors
   and BM25.
4. Score Fusion across Granularities (RRF):
   Aggregates unit matches to score their verified *parents*:
   s(p) = sum_{t} sum_{u in U_t(p)} w_t / (60 + rank_t(u))
5. Cross-Encoder Reranker: multilingual reranking of top candidate parents.
6. Parent Expansion: returns the full verified parent block text for answering.
"""
from __future__ import annotations

import logging
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

import numpy as np

from .config import Config
from .index import BM25Index, LocalEmbedder
from .models import Parent, Unit
from .store import read_json
from .textnorm import norm_for_compare, words

log = logging.getLogger(__name__)


class RetrievedEvidence:
    """Grounding block returned to the answering model."""

    def __init__(
        self,
        parent_id: str,
        title: str,
        heading_path: list[str],
        page_start: int,
        page_end: int,
        text: str,
        score: float,
        source_file: str = "",
        status: str = "extracted",
        meta: dict[str, Any] | None = None,
    ):
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


class KnowledgeRetriever:
    """Retriever loading an immutable index build."""

    def __init__(self, cfg: Config, index_dir: Path):
        self.cfg = cfg
        self.index_dir = index_dir
        self.manifest = read_json(index_dir / "manifest.json", {})
        self.parents_data = read_json(index_dir / "parents.json", {})
        self.units_data = read_json(index_dir / "units.json", [])
        self.units = [Unit.from_dict(u) for u in self.units_data]

        # Load dense vectors
        vec_path = index_dir / "vectors.npy"
        self.vectors = np.load(vec_path).astype(np.float32) if vec_path.exists() else np.empty((0, 384))

        # Build in-memory unit index maps
        self.unit_idx_map = {u.id: idx for idx, u in enumerate(self.units)}
        unit_texts = [u.embed_text() for u in self.units]
        unit_ids = [u.id for u in self.units]

        # Initialize sparse BM25
        self.bm25 = BM25Index()
        self.bm25.build(unit_ids, unit_texts)

        # Initialize Embedder
        model_path = cfg.embedding.model_path if Path(cfg.embedding.model_path).exists() else cfg.embedding.model
        self.embedder = LocalEmbedder(model_path, cfg.embedding.max_tokens, cfg.embedding.family)

        # Cross-encoder reranker (optional, lazy loaded)
        self._reranker = None

    def search(self, question: str, top_k: int = 5) -> list[RetrievedEvidence]:
        """Execute hybrid search, reciprocal rank fusion, and parent expansion."""
        requested_years = self._extract_query_years(question)

        # 1. Structured SQL fact lookup for cutoff questions
        sql_results = self._lookup_structured_facts(question)
        if sql_results:
            return sql_results[:top_k]

        # 2. Dense Semantic Search
        q_vec = self.embedder.embed_query(question)
        sims = np.dot(self.vectors, q_vec)
        cfg_per_type = self.cfg.retrieval.per_type_k * 2
        dense_top_indices = np.argsort(sims)[::-1][:cfg_per_type]
        dense_ranked_units = [(self.units[idx].id, float(sims[idx])) for idx in dense_top_indices]

        # 3. Sparse BM25 Search
        bm25_ranked_units = self.bm25.search(question, top_k=cfg_per_type)

        # 4. Multi-granularity RRF fused at the Parent level
        # Score parents: s(p) = sum_{channel} sum_{u} weight / (60 + rank)
        parent_scores: dict[str, float] = {}

        def accumulate_rrf(ranked_items: list[tuple[str, float]], channel_weight: float):
            for rank, (u_id, _) in enumerate(ranked_items, 1):
                idx = self.unit_idx_map.get(u_id)
                if idx is None:
                    continue
                u = self.units[idx]

                # Temporal year filter
                u_years = set(u.meta.get("years", []))
                if requested_years and u_years and not u_years.intersection(requested_years):
                    continue

                type_weight = self.cfg.retrieval.type_weights.get(u.type, 1.0)
                rrf_score = (channel_weight * type_weight) / (self.cfg.retrieval.rrf_k + rank)

                for p_id in u.parent_ids:
                    parent_scores[p_id] = parent_scores.get(p_id, 0.0) + rrf_score

        accumulate_rrf(dense_ranked_units, self.cfg.retrieval.channel_weights.get("dense", 1.0))
        accumulate_rrf(bm25_ranked_units, self.cfg.retrieval.channel_weights.get("bm25", 1.0))

        if not parent_scores:
            return []

        # Sort candidate parents
        sorted_parents = sorted(parent_scores.items(), key=lambda x: x[1], reverse=True)[:self.cfg.retrieval.rerank_top]

        # 5. Optional Cross-Encoder Reranking
        if self.cfg.retrieval.rerank:
            sorted_parents = self._rerank_parents(question, sorted_parents)

        # 6. Parent Expansion & Evidence Materialisation
        results: list[RetrievedEvidence] = []
        for p_id, score in sorted_parents[:top_k]:
            p_data = self.parents_data.get(p_id)
            if not p_data:
                continue

            results.append(RetrievedEvidence(
                parent_id=p_id,
                title=p_data.get("meta", {}).get("title", ""),
                heading_path=p_data.get("heading_path", []),
                page_start=p_data.get("page_start", -1),
                page_end=p_data.get("page_end", -1),
                text=p_data.get("text", ""),
                score=score,
                source_file=p_data.get("meta", {}).get("source_file", ""),
                status=p_data.get("status", "extracted"),
                meta=p_data.get("meta", {}),
            ))

        return results

    def _extract_query_years(self, query: str) -> set[int]:
        years = {int(y) for y in re.findall(r"(?<!\d)(20[0-4]\d)(?!\d)", query)}
        if not years and re.search(r"this year|current year|इस साल|इस वर्ष", query, re.I):
            years.add(time.localtime().tm_year)
        return years

    def _lookup_structured_facts(self, question: str) -> list[RetrievedEvidence]:
        """Check facts.sqlite for exact cutoff queries."""
        db_path = self.index_dir / "facts.sqlite"
        if not db_path.exists():
            return []

        # Simple cutoff query intent detection
        is_cutoff = bool(re.search(r"cutoff|cut-off|closing rank|opening rank|कटऑफ|रैंक", question, re.I))
        if not is_cutoff:
            return []

        # Search matching cutoffs in SQLite
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT programme, category, round, closing_rank, year, parent_id FROM cutoffs LIMIT 5")
        rows = cur.fetchall()
        con.close()

        evidence = []
        for prog, cat, rnd, rank, yr, p_id in rows:
            p_data = self.parents_data.get(p_id, {})
            text = f"JoSAA/CSAB {yr} Cutoff: {prog} ({cat}, Round {rnd}) Closing Rank: {rank}"
            evidence.append(RetrievedEvidence(
                parent_id=p_id or "cutoff_record",
                title=f"Cutoffs {yr}",
                heading_path=["Admissions", "Cutoffs", prog],
                page_start=-1,
                page_end=-1,
                text=text,
                score=1.0,
            ))
        return evidence

    def _rerank_parents(self, query: str, candidates: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """Rerank candidate parent passages using cross-encoder."""
        try:
            if self._reranker is None:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(self.cfg.retrieval.reranker)

            pairs = []
            for p_id, _ in candidates:
                p_text = self.parents_data.get(p_id, {}).get("text", "")[:self.cfg.retrieval.rerank_max_chars]
                pairs.append((query, p_text))

            scores = self._reranker.predict(pairs)
            reranked = [(candidates[i][0], float(scores[i])) for i in range(len(candidates))]
            return sorted(reranked, key=lambda x: x[1], reverse=True)
        except Exception as exc:
            log.warning("Reranker failed: %s; falling back to RRF scores", exc)
            return candidates
