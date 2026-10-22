#!/usr/bin/env python3
"""04_demo2_latency.py — Colab (T2) launcher for Demo2's latency benchmark.

The benchmark itself lives in code/demo2/evaluate_latency.py (single source of
truth, unit-tested in code/demo2/tests/test_evaluate_latency.py). This wrapper
only locates demo2 in the Colab clone, labels the run T2 and writes into
/content/colab_out/ so colab_go.sh can download it.

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
import os
import sys
from pathlib import Path

OUT = Path(os.getenv("COLAB_OUT", "/content/colab_out"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, help="Timed turns (default: one pass of demo2's question set).")
    ap.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    ap.add_argument("--warmup", action="store_true", help="One untimed warm-up turn (outside the timed set).")
    ap.add_argument("--out", default="demo2_latency_summary.json", help="Output file name inside COLAB_OUT.")
    ap.add_argument("--keep-cache", action="store_true", help="Reuse demo2's data dir (warm caches).")
    ap.add_argument("--tier", default="T2")
    args = ap.parse_args()

    demo2 = Path(os.getenv("DEMO2_DIR", "/content/minor/code/demo2")).resolve()
    if not (demo2 / "evaluate_latency.py").is_file():
        sys.exit(f"{demo2}/evaluate_latency.py not found. Set DEMO2_DIR or pull the latest repo.")
    os.chdir(demo2)
    sys.path.insert(0, str(demo2))
    import evaluate_latency  # noqa: E402

    argv = ["--output", str(OUT / args.out), "--provider", args.provider, "--tier", args.tier]
    argv += ["--turns", str(args.turns)] if args.turns else []
    argv += ["--warmup"] if args.warmup else []
    argv += ["--keep-cache"] if args.keep_cache else []
    evaluate_latency.main(argv)


if __name__ == "__main__":
    main()
