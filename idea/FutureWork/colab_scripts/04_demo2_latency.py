#!/usr/bin/env python3
"""04_demo2_latency.py — headless Demo2 turn-latency runner for Colab (T2).

Runs the real grounded agent (no Streamlit UI) over a small question set and
records wall-clock latency per turn, response status, source files, the answer
text and any llm_error. It calls agent_bridge.ask(...) exactly as the app does.

This is the Colab replacement for the T0 120-turn benchmark, kept SHORT by
default (one pass over the built-in set) so it fits a Colab session; raise
--turns to cycle the set more than once.

The warm-up turn uses a question that is NOT in the timed set, so no timed turn
gets a retrieval/draft cache hit from the warm-up. Every timed turn uses a new
session id (no history). Repeating a question (turns > set size) WILL hit the
retrieval cache; those rows are marked repeat=true and excluded from the
"first_pass" stats.

Prereqs (run first):
    bash 01_bootstrap.sh
    bash 02_serve_config.sh
    set -a; source /content/colab_out/.env.colab; set +a

Usage:
    python 04_demo2_latency.py --warmup --provider ollama
    python 04_demo2_latency.py --warmup --provider groq --out demo2_latency_groq_summary.json
Writes /content/colab_out/<--out> (default demo2_latency_summary.json)
"""
import argparse
import json
import math
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

OUT = Path(os.getenv("COLAB_OUT", "/content/colab_out"))

# Untimed warm-up question: deliberately outside QUESTIONS (no shared cache keys).
WARMUP_QUESTION = "Where is IIIT Naya Raipur located?"

# A representative, grounded question set (Hindi, English, Hinglish). These
# exercise the full route -> retrieve -> generate -> review path.
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


def pct(values, q):
    """Nearest-rank percentile (q in 0..100). With small n, p95 == max."""
    if not values:
        return None
    s = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(s)))
    return round(s[rank - 1], 3)


def stats(values):
    if not values:
        return {"n": 0, "median": None, "p95": None, "min": None, "max": None}
    return {"n": len(values), "median": round(statistics.median(values), 3),
            "p95": pct(values, 95), "min": round(min(values), 3), "max": round(max(values), 3)}


def source_names(sources):
    names = []
    for s in sources or []:
        if isinstance(s, dict):
            name = s.get("source_file") or s.get("source") or s.get("title") or "?"
            page = s.get("page_number", s.get("page"))
            names.append(f"{name}" + (f" p{page}" if page not in (None, -1) else ""))
        else:
            names.append(str(s))
    return names


def run_turn(agent_bridge, q, profile, provider):
    t0 = time.time()
    row = {"question": q, "status": "error", "sources": 0, "source_files": [],
           "language": None, "answer_text": None, "llm_error": None,
           "rag_metrics": {}, "error": None}
    try:
        r = agent_bridge.ask(q, str(uuid4()), profile, provider=provider)
        row.update(
            status=r.get("response_status"),
            sources=len(r.get("sources") or []),
            source_files=source_names(r.get("sources"))[:8],
            language=r.get("language"),
            answer_text=(r.get("answer_text") or "")[:400],
            llm_error=r.get("llm_error") or None,
            rag_metrics=r.get("rag_metrics") or {},
        )
    except Exception as e:  # keep going; the summary records the failure
        row["error"] = f"{type(e).__name__}: {e}"
    row["wall_s"] = round(time.time() - t0, 3)
    return row


def stage_medians(rows):
    """Median per stage_ms key across rows (ms)."""
    keys = sorted({k for r in rows for k in (r["rag_metrics"].get("stage_ms") or {})})
    out = {}
    for k in keys:
        vals = [r["rag_metrics"]["stage_ms"][k] for r in rows
                if k in (r["rag_metrics"].get("stage_ms") or {})]
        out[k] = round(statistics.median(vals), 1) if vals else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=len(QUESTIONS),
                    help=f"Timed turns (cycles the {len(QUESTIONS)}-question set; default one pass).")
    ap.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    ap.add_argument("--warmup", action="store_true",
                    help="Run one untimed warm-up turn first (question outside the timed set).")
    ap.add_argument("--out", default="demo2_latency_summary.json",
                    help="Output file name inside COLAB_OUT.")
    ap.add_argument("--keep-cache", action="store_true",
                    help="Reuse DEMO2_DATA_DIR (or demo2's default data dir) instead of a fresh one.")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    # Fresh demo2 runtime dir per run: the RAG cache (TTL 1 h) and checkpoints live
    # in DEMO2_DATA_DIR, and the Colab VM persists between colab_go.sh runs, so
    # without this a re-run would report draft-cache hits as model latency. Also
    # keeps benchmark state out of code/demo2/data (FutureWork/AGENTS.md).
    if not args.keep_cache:
        os.environ["DEMO2_DATA_DIR"] = tempfile.mkdtemp(prefix="demo2_latency_", dir=str(OUT))
    print(f"DEMO2_DATA_DIR = {os.getenv('DEMO2_DATA_DIR', '(demo2 default: code/demo2/data)')}")

    # Demo2 imports are relative to its own directory; make them importable.
    DEMO2 = Path(os.getenv("DEMO2_DIR", "/content/minor/code/demo2")).resolve()
    if not (DEMO2 / "agent_bridge.py").is_file():
        sys.exit(f"demo2 not found at {DEMO2}. Set DEMO2_DIR or run 01_bootstrap.sh.")
    os.chdir(DEMO2)
    sys.path.insert(0, str(DEMO2))

    import agent_bridge  # noqa: E402  (after sys.path/chdir)

    profile = {"student_id": "guest", "student_email": "", "student_category": "general"}

    warmup = None
    if args.warmup:
        print(f"Warm-up turn (untimed): {WARMUP_QUESTION}")
        warmup = run_turn(agent_bridge, WARMUP_QUESTION, profile, args.provider)
        print(f"  warm-up: {warmup['wall_s']}s  status={warmup['status']}"
              + (f"  ERROR={warmup['error']}" if warmup["error"] else ""))

    results = []
    n = max(1, args.turns)
    for i in range(n):
        q = QUESTIONS[i % len(QUESTIONS)]
        row = {"i": i, "repeat": i >= len(QUESTIONS), **run_turn(agent_bridge, q, profile, args.provider)}
        results.append(row)
        print(f"  turn {i+1}/{n}: {row['wall_s']}s  status={row['status']}  sources={row['sources']}"
              + (f"  llm_error={row['llm_error']}" if row["llm_error"] else "")
              + (f"  ERROR={row['error']}" if row["error"] else ""))

    ok = [r for r in results if r["error"] is None]
    first = [r for r in ok if not r["repeat"]]
    answered = [r for r in ok if r["status"] == "answered"]
    by_status = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    summary = {
        "tier": "T2",
        "provider": args.provider,
        "model": next((r["rag_metrics"].get("model") for r in ok if r["rag_metrics"].get("model")), None),
        "turns": n,
        "data_dir": os.getenv("DEMO2_DATA_DIR"),
        "answered": len(answered),
        "status_counts": by_status,
        "wall_s_all": stats([r["wall_s"] for r in ok]),
        "wall_s_first_pass": stats([r["wall_s"] for r in first]),
        "wall_s_answered": stats([r["wall_s"] for r in answered]),
        "stage_ms_median_answered": stage_medians(answered),
        # Kept for backward compatibility with earlier summaries.
        "wall_s_median": stats([r["wall_s"] for r in ok])["median"],
        "warmup": warmup,
        "results": results,
        "note": ("T0 baseline median answered text turn was 18.7 s (p95 29.9 s), n=120. "
                 "p95 here is nearest-rank; with n<20 it equals the max."),
    }
    path = OUT / args.out
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    a = summary["wall_s_answered"]
    print(f"\nAnswered {len(answered)}/{n}  status={by_status}")
    print(f"Answered turns: median {a['median']} s  p95 {a['p95']} s  (n={a['n']})")
    print(f"All turns:      median {summary['wall_s_all']['median']} s")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
