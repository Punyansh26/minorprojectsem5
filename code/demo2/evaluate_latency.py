"""Headless grounded-turn latency benchmark for Demo2 on any hardware tier.

Calls agent_bridge.ask(...) exactly as the app does (no UI, no speech) over a fixed
public question set and writes one JSON summary: wall time per turn, response status,
cited sources, answer text, llm_error and the agent's own rag_metrics.

Measurement rules (why the numbers are comparable between runs and machines):
  * The warm-up question is outside the timed set, so no timed turn reuses its caches.
  * Every timed turn gets a new session id (no conversation history).
  * Runtime state (RAG cache, checkpoints, tickets) goes to a fresh temporary
    DEMO2_DATA_DIR unless --keep-cache is given. The RAG cache has a 1 h TTL, so a
    re-run on the same machine would otherwise report draft-cache hits as model time.
    This also keeps benchmark state out of code/demo2/data.
  * Turns beyond one pass of the set are flagged repeat=true (they hit the retrieval
    cache) and excluded from wall_s_first_pass.
  * p95 uses stats.p95 (linear interpolation, same as every other Demo2 report).

Usage:
    python evaluate_latency.py --output /tmp/latency/summary.json --warmup
    python evaluate_latency.py --output out.json --warmup --provider groq --tier T2
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import stats

# Untimed warm-up question: deliberately outside QUESTIONS (no shared cache keys).
WARMUP_QUESTION = "Where is IIIT Naya Raipur located?"

# Public, grounded questions (Hindi, English, Hinglish) that exercise
# route -> retrieve -> generate -> review.
QUESTIONS = [
    "बी टेक में प्रवेश किस आधार पर होता है?",
    "What documents are required for admission?",
    "Is hostel accommodation available for first year students?",
    "फीस कितनी है?",
    "Which B.Tech branches does the institute offer?",
    "IIIT Naya Raipur kis university se affiliated hai?",
    "What is the application fee for B.Tech admission?",
    "हॉस्टल में कौन-कौन सी सुविधाएं हैं?",
]

BASELINE_NOTE = ("T0 baseline (RTX 4060 Laptop, qwen3.5:9b, 45/55 CPU/GPU split): median answered "
                 "text turn 18.7 s, p95 29.9 s, n=120. With n<20 the p95 here is close to the max.")


def summarize_wall(values: list[float]) -> dict:
    """n, median, p95, min and max of a list of wall times (None fields when empty)."""
    if not values:
        return {"n": 0, "median": None, "p95": None, "min": None, "max": None}
    return {"n": len(values), "median": round(stats.median(values), 3), "p95": round(stats.p95(values), 3),
            "min": round(min(values), 3), "max": round(max(values), 3)}


def source_names(sources) -> list[str]:
    """Readable 'file pN' labels for the citations the agent returned."""
    names = []
    for source in sources or []:
        if isinstance(source, dict):
            page = source.get("page_number")
            names.append(str(source.get("source_file") or "?") + (f" p{page}" if page not in (None, -1) else ""))
        else:
            names.append(str(source))
    return names


def stage_medians(rows: list[dict]) -> dict:
    """Median of each rag_metrics.stage_ms key (ms) over the given rows."""
    keys = sorted({key for row in rows for key in (row["rag_metrics"].get("stage_ms") or {})})
    out = {}
    for key in keys:
        values = [row["rag_metrics"]["stage_ms"][key] for row in rows
                  if key in (row["rag_metrics"].get("stage_ms") or {})]
        out[key] = round(stats.median(values), 1)
    return out


def build_summary(results: list[dict], *, provider: str, tier: str, warmup: dict | None,
                  data_dir: str | None) -> dict:
    """Aggregate per-turn rows into the summary written to --output."""
    ok = [row for row in results if row["error"] is None]
    # Repeats are cache hits; keep them out of the answered-latency statistics.
    answered = [row for row in ok if row["status"] == "answered" and not row["repeat"]]
    status_counts: dict[str, int] = {}
    for row in results:
        status_counts[str(row["status"])] = status_counts.get(str(row["status"]), 0) + 1
    return {
        "tier": tier,
        "provider": provider,
        "model": next((row["rag_metrics"].get("model") for row in ok if row["rag_metrics"].get("model")), None),
        "turns": len(results),
        "answered": sum(1 for row in ok if row["status"] == "answered"),
        "status_counts": status_counts,
        "wall_s_all": summarize_wall([row["wall_s"] for row in ok]),
        "wall_s_first_pass": summarize_wall([row["wall_s"] for row in ok if not row["repeat"]]),
        "wall_s_answered": summarize_wall([row["wall_s"] for row in answered]),
        "stage_ms_median_answered": stage_medians(answered),
        "wall_s_median": summarize_wall([row["wall_s"] for row in ok])["median"],  # older summaries' key
        "data_dir": data_dir,
        "warmup": warmup,
        "results": results,
        "note": BASELINE_NOTE,
    }


def run_turn(ask, question: str, profile: dict, provider: str) -> dict:
    """One timed agent turn in a fresh session; failures are recorded, not raised."""
    started = time.perf_counter()
    row = {"question": question, "status": "error", "sources": 0, "source_files": [], "language": None,
           "answer_text": None, "llm_error": None, "rag_metrics": {}, "error": None}
    try:
        result = ask(question, str(uuid4()), profile, provider=provider)
        row.update(status=result.get("response_status"), sources=len(result.get("sources") or []),
                   source_files=source_names(result.get("sources"))[:8], language=result.get("language"),
                   answer_text=(result.get("answer_text") or "")[:400], llm_error=result.get("llm_error") or None,
                   rag_metrics=result.get("rag_metrics") or {})
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["wall_s"] = round(time.perf_counter() - started, 3)
    return row


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True, help="Summary JSON path")
    parser.add_argument("--turns", type=int, default=len(QUESTIONS),
                        help=f"Timed turns, cycling the {len(QUESTIONS)}-question set (default: one pass)")
    parser.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    parser.add_argument("--warmup", action="store_true", help="One untimed turn first (question outside the set)")
    parser.add_argument("--tier", default="T0", help="Hardware tier label recorded in the summary (T0/T1/T2)")
    parser.add_argument("--keep-cache", action="store_true",
                        help="Use the configured DEMO2_DATA_DIR (warm caches) instead of a fresh temporary one")
    args = parser.parse_args(argv)
    if args.turns < 1:
        parser.error("--turns must be positive")

    scratch = None
    if not args.keep_cache:
        # Must precede the first `settings` import (agent_bridge below), which reads it.
        scratch = tempfile.mkdtemp(prefix="demo2_latency_")
        os.environ["DEMO2_DATA_DIR"] = scratch
    import agent_bridge  # noqa: E402  (deliberately after DEMO2_DATA_DIR is fixed)
    import settings as cfg
    print(f"DEMO2_DATA_DIR = {cfg.DATA_ROOT}", flush=True)

    profile = {"student_id": "guest", "student_email": "", "student_category": "general"}
    try:
        warmup = None
        if args.warmup:
            warmup = run_turn(agent_bridge.ask, WARMUP_QUESTION, profile, args.provider)
            print(f"warm-up: {warmup['wall_s']}s status={warmup['status']}"
                  + (f" ERROR={warmup['error']}" if warmup["error"] else ""), flush=True)
        results = []
        for index in range(args.turns):
            row = {"i": index, "repeat": index >= len(QUESTIONS),
                   **run_turn(agent_bridge.ask, QUESTIONS[index % len(QUESTIONS)], profile, args.provider)}
            results.append(row)
            print(f"turn {index + 1}/{args.turns}: {row['wall_s']}s status={row['status']} sources={row['sources']}"
                  + (f" llm_error={row['llm_error']}" if row["llm_error"] else "")
                  + (f" ERROR={row['error']}" if row["error"] else ""), flush=True)
        summary = build_summary(results, provider=args.provider, tier=args.tier, warmup=warmup,
                                data_dir="fresh temporary (deleted)" if scratch else str(cfg.DATA_ROOT))
    finally:
        if scratch:
            # Open SQLite handles are harmless here: Linux unlinks, atexit closes them later.
            shutil.rmtree(scratch, ignore_errors=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    answered = summary["wall_s_answered"]
    print(f"\nAnswered {summary['answered']}/{summary['turns']} {summary['status_counts']}")
    print(f"Answered turns: median {answered['median']} s, p95 {answered['p95']} s (n={answered['n']})")
    print(f"Wrote {args.output}")
    return summary


if __name__ == "__main__":
    main()
