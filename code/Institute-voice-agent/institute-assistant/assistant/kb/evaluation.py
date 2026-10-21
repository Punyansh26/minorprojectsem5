"""Measure supporting-evidence recall and exact rank accuracy against reviewed questions."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from unittest.mock import patch

from assistant.kb.common import now, read_json, write_json
from assistant.kb.search import SearchEngine
from assistant.kb.structured import lookup_cutoffs


def evaluate_release(root: Path, cases_path: Path, baseline: bool = False) -> dict:
    """Write a release gate from measured results, never from status labels alone."""
    cases = read_json(cases_path, [])
    if len(cases) < 90:
        raise ValueError("At least 90 source-checked cases are required")
    engine = SearchEngine(root, read_json(root / "release.json"))
    engine.embeddings.embed_query("warmup")
    records, latencies = [], []
    old_retrieve = None
    if baseline:
        from assistant import retrieval
        retrieval._VECTORSTORE = retrieval._get_vectorstore()
        old_retrieve = retrieval.retrieve
    for case in cases:
        started = time.monotonic()
        hits = engine.search(case["question"], 6)
        latencies.append(time.monotonic() - started)
        expected = set(case.get("expected_blocks", []))
        ids = {h.block_id for h in hits}
        evidence_ids = ids | {engine.parents.get(key, {}).get("evidence_block_id", key) for key in ids}
        terms = case.get("required_terms", [])
        text = "\n".join(h.text for h in hits)
        if case["expected"] == "answerable":
            passed = bool(evidence_ids & expected) and all(term.casefold() in text.casefold() for term in terms)
        elif case["expected"] == "no_cutoff":
            passed = not hits
        else:
            # Unknown ordinary questions are evaluated for answer abstention separately;
            # vector retrieval returning related context is not proof of a false answer.
            passed = None
        if case.get("cutoff_filters"):
            rows = lookup_cutoffs(root / "facts.sqlite", case["cutoff_filters"])
            exact = any(str(r["opening_rank"]) == case["opening_rank"] and str(r["closing_rank"]) == case["closing_rank"] for r in rows)
            passed = passed and exact
        row = {"id": case["id"], "question": case["question"], "expected": case["expected"], "passed": passed,
               "retrieved_blocks": list(ids), "seconds": round(latencies[-1], 4)}
        if old_retrieve:
            # Cached legacy stores never override the active release in normal serving.
            with patch("assistant.retrieval.get_release_engine", return_value=None):
                old_hits = old_retrieve(case["question"])
            reference = [engine.parents[key] for key in expected if key in engine.parents]
            row["baseline_recalled"] = bool(reference) and any(Path(h.source_file).name == Path(b["source_file"]).name and h.page_number == b["page_number"] for h in old_hits for b in reference)
        records.append(row)
    answerable = [r for r in records if r["expected"] == "answerable"]
    recall = sum(r["passed"] for r in answerable) / max(1, len(answerable))
    exact_cases = [r for r, c in zip(records, cases) if c.get("cutoff_filters") or c["expected"] == "no_cutoff"]
    report = {"generated_at": now(), "cases_sha256": __import__('hashlib').sha256(cases_path.read_bytes()).hexdigest(),
              "cases": len(cases), "answerable_cases": len(answerable), "recall_at_6": round(recall, 4),
              "exact_rank_cases": len(exact_cases), "exact_rank_passed": sum(r["passed"] for r in exact_cases),
              "abstention_cases_requiring_answer_review": sum(r["passed"] is None for r in records),
              "median_seconds": round(statistics.median(latencies), 4),
              "p95_seconds": round(sorted(latencies)[int(.95 * (len(latencies)-1))], 4),
              "passed": recall >= .90 and all(r["passed"] for r in exact_cases), "results": records}
    manifest = read_json(root / "release.json")
    if manifest.get("manifest_version",1) >= 2:
        from assistant.kb.integrity import verify, content_digest
        verify(root,manifest)
        report["content_digest"] = content_digest(manifest["content_sha256"])
    if baseline:
        report["baseline_recall_at_6"] = round(sum(r.get("baseline_recalled", False) for r in answerable) / max(1, len(answerable)), 4)
        from assistant import retrieval
        retrieval._VECTORSTORE = None
        retrieval._LEXICAL_CACHE = None
    write_json(root / "validation.json", report)
    return {k: v for k, v in report.items() if k != "results"}
