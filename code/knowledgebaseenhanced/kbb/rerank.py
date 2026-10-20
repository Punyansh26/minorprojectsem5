"""Cross-encoder reranking of the fused shortlist (FutureWork chapter 04 §7).

The hybrid channel (dense + BM25 fused by RRF) is near its recall ceiling on the spot-check set but its
*ordering* is weaker (measured with ``scripts/spotcheck.py`` on release 20261014T005813186766Z, answerable
cases: pass@1 91/127, pass@3 113/127, pass@6 125/127, MRR 0.823).  A
cross-encoder reads (question, unit) jointly and fixes ordering errors fusion cannot.

Contract, in order of importance:

* **Retrieval-only.**  The reranker reorders parent ids.  It never edits evidence text, and it never
  runs on the policy, exact-cutoff or matched-record paths (``ReleaseSearch.search`` returns or places
  those before fusion).
* **Never worse than off.**  Disabled by default.  If the model is missing (only local files are read;
  nothing is downloaded), fails to load, raises, is still busy with an earlier query, or exceeds
  ``budget_s``, ``rerank`` returns ``None`` and the caller keeps the fusion order.
* **Bounded.**  One worker thread; a query that overruns the budget is abandoned (the caller moves on)
  and later queries skip reranking until that worker is free, so slow inference cannot pile up.
* **CPU on T0.**  The default device is CPU so the model never competes with the resident 9B LLM for the
  8 GB GPU (chapter 01 §4.3).
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Callable, Sequence

log = logging.getLogger(__name__)

ScoreFn = Callable[[list[tuple[str, str]]], Sequence[float]]


class Reranker:
    """Lazy, latency-gated cross-encoder.  ``loader`` is injectable for tests."""

    def __init__(self, model: str, *, max_chars: int = 2000, budget_s: float = 1.5, device: str = "cpu",
                 batch_size: int = 16, loader: Callable[[], ScoreFn] | None = None):
        self.model, self.max_chars, self.budget_s = model, max_chars, budget_s
        self.device, self.batch_size = device, batch_size
        self._loader = loader or self._load_cross_encoder
        self._score: ScoreFn | None = None
        self._load_error = ""
        self._loaded = False
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kbb-rerank")
        self._inflight = None
        self.last: dict = {"status": "unused"}

    def _load_cross_encoder(self) -> ScoreFn:
        from sentence_transformers import CrossEncoder
        encoder = CrossEncoder(self.model, device=self.device, local_files_only=True, max_length=512)
        return lambda pairs: encoder.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)

    def _ensure_loaded(self) -> bool:
        with self._lock:
            if not self._loaded:
                self._loaded = True
                try:
                    self._score = self._loader()
                except Exception as error:          # missing/incomplete weights, bad install ...
                    self._score = None
                    self._load_error = f"{type(error).__name__}: {error}"
                    log.warning("reranker unavailable, keeping fusion order: %s", self._load_error)
            return self._score is not None

    def warm(self) -> bool:
        """Load the model ahead of the first query (optional)."""
        return self._ensure_loaded()

    def rerank(self, question: str, candidates: list[tuple[str, str]]) -> list[str] | None:
        """Return candidate ids ordered by cross-encoder score, or ``None`` to keep the caller's order."""
        started = time.monotonic()
        if len(candidates) < 2:
            self.last = {"status": "skipped", "n": len(candidates), "ms": 0.0}
            return None
        if not self._ensure_loaded():
            self.last = {"status": "unavailable", "reason": self._load_error, "ms": 0.0}
            return None
        if self._inflight is not None and not self._inflight.done():
            self.last = {"status": "busy", "ms": 0.0}
            return None
        pairs = [(question, text[: self.max_chars]) for _, text in candidates]
        self._inflight = self._pool.submit(self._score, pairs)
        remaining = self.budget_s - (time.monotonic() - started)
        try:
            scores = [float(s) for s in self._inflight.result(timeout=max(0.0, remaining))]
        except FutureTimeout:
            self.last = {"status": "timeout", "n": len(pairs), "ms": round((time.monotonic() - started) * 1000, 1)}
            return None
        except Exception as error:
            self.last = {"status": "error", "reason": f"{type(error).__name__}: {error}",
                         "ms": round((time.monotonic() - started) * 1000, 1)}
            return None
        if len(scores) != len(candidates):
            self.last = {"status": "error", "reason": "score count mismatch", "ms": 0.0}
            return None
        # Stable sort: equal scores keep the fusion order.
        order = sorted(range(len(candidates)), key=lambda i: -scores[i])
        self.last = {"status": "ok", "n": len(pairs), "ms": round((time.monotonic() - started) * 1000, 1)}
        return [candidates[i][0] for i in order]
