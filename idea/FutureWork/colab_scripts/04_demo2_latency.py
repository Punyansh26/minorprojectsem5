#!/usr/bin/env python3
"""04_demo2_latency.py — headless Demo2 turn-latency runner for Colab (T2).

Runs the real grounded agent (no Streamlit UI) over a small question set and
records wall-clock latency per turn plus the response status and source count.
It calls agent_bridge.ask(...) exactly as the app does.

This is the Colab replacement for the T0 120-turn benchmark, kept SHORT by
default (a few questions) so it fits a Colab session; raise --turns to stress it.

Prereqs (run first):
    bash 01_bootstrap.sh
    bash 02_serve_config.sh
    set -a; source /content/colab_out/.env.colab; set +a

Usage:
    python 04_demo2_latency.py --turns 2 --provider ollama
Writes /content/colab_out/demo2_latency_summary.json
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from uuid import uuid4

OUT = Path(os.getenv("COLAB_OUT", "/content/colab_out"))

# A representative, grounded question set (Hindi + English). These exercise the
# full retrieve->generate->verify path.
QUESTIONS = [
    "बी टेक में प्रवेश किस आधार पर होता है?",
    "What documents are required for admission?",
    "Is hostel accommodation available for first year students?",
    "फीस कितनी है?",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=2,
                    help="Questions to run (1..len of the built-in set, cycled).")
    ap.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    ap.add_argument("--warmup", action="store_true", help="Run one untimed warm-up turn first.")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    # Demo2 imports are relative to its own directory; make them importable.
    DEMO2 = Path(os.getenv("DEMO2_DIR", "/content/minor/code/demo2")).resolve()
    if not (DEMO2 / "agent_bridge.py").is_file():
        sys.exit(f"demo2 not found at {DEMO2}. Set DEMO2_DIR or run 01_bootstrap.sh.")
    os.chdir(DEMO2)
    sys.path.insert(0, str(DEMO2))

    import agent_bridge  # noqa: E402  (after sys.path/chdir)

    profile = {"student_id": "guest", "student_email": "", "student_category": "general"}

    if args.warmup:
        print("Warm-up turn (untimed)...")
        try:
            agent_bridge.ask(QUESTIONS[0], str(uuid4()), profile, provider=args.provider)
        except Exception as e:
            print(f"  warm-up error: {e}")

    results = []
    n = max(1, args.turns)
    for i in range(n):
        q = QUESTIONS[i % len(QUESTIONS)]
        sid = str(uuid4())
        t0 = time.time()
        status, nsrc, err = "error", 0, None
        try:
            r = agent_bridge.ask(q, sid, profile, provider=args.provider)
            status = r.get("response_status")
            nsrc = len(r.get("sources") or [])
            # rag_metrics may carry per-stage timings if the agent records them.
            metrics = r.get("rag_metrics") or {}
        except Exception as e:
            err, metrics = str(e), {}
        wall = round(time.time() - t0, 3)
        row = {"i": i, "question": q, "wall_s": wall, "status": status,
               "sources": nsrc, "rag_metrics": metrics, "error": err}
        results.append(row)
        print(f"  turn {i+1}/{n}: {wall}s  status={status}  sources={nsrc}"
              + (f"  ERROR={err}" if err else ""))

    walls = [r["wall_s"] for r in results if r["error"] is None]
    summary = {
        "tier": "T2",
        "provider": args.provider,
        "turns": n,
        "answered": sum(1 for r in results if r["status"] == "answered"),
        "wall_s_median": round(statistics.median(walls), 3) if walls else None,
        "wall_s_min": min(walls) if walls else None,
        "wall_s_max": max(walls) if walls else None,
        "results": results,
        "note": ("T0 baseline median answered text turn was 18.7 s (p95 29.9 s). "
                 "On A100 with the model fully on GPU, expect substantially lower."),
    }
    path = OUT / "demo2_latency_summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nMedian turn: {summary['wall_s_median']} s  "
          f"({summary['answered']}/{n} answered)")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
