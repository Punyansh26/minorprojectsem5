#!/usr/bin/env python3
"""03_benchmark_decode.py — Tier T2 (A100/A80) decode-speed + model-fit benchmark.

Replaces the T0 "L0" test. On an A100 the model fits fully on the GPU, so this
measures the *achievable* decode speed (tok/s) and prompt-eval speed, over a few
warm repeats, and records the GPU residency split.

Writes /content/colab_out/benchmark_decode_summary.json

Usage:
    python 03_benchmark_decode.py --model qwen3.5:9b --repeats 5
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

OUT = Path(os.getenv("COLAB_OUT", "/content/colab_out"))
OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def _post(path, payload, timeout=600):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def gpu_info():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free",
             "--format=csv,noheader"], text=True).strip()
        return out
    except Exception as e:
        return f"nvidia-smi unavailable: {e}"


def ollama_ps():
    try:
        return subprocess.check_output(["ollama", "ps"], text=True).strip()
    except Exception as e:
        return f"ollama ps unavailable: {e}"


def run_once(model, prompt, num_predict):
    """One non-streaming generate; returns Ollama's own timing counters."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0},
    }
    t0 = time.time()
    resp = _post("/api/generate", payload)
    wall = time.time() - t0
    # Ollama returns nanosecond counters.
    eval_count = resp.get("eval_count", 0)
    eval_ns = resp.get("eval_duration", 0) or 1
    pe_count = resp.get("prompt_eval_count", 0)
    pe_ns = resp.get("prompt_eval_duration", 0) or 1
    load_ns = resp.get("load_duration", 0)
    return {
        "wall_s": round(wall, 3),
        "decode_tok_s": round(eval_count / (eval_ns / 1e9), 2),
        "prompt_eval_tok_s": round(pe_count / (pe_ns / 1e9), 2),
        "eval_count": eval_count,
        "prompt_eval_count": pe_count,
        "load_s": round(load_ns / 1e9, 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--num-predict", type=int, default=256)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    prompt = ("You are a helpful assistant. Write a clear, detailed paragraph "
              "explaining how retrieval-augmented generation works, step by step.")

    print(f"GPU: {gpu_info()}")
    print(f"Model: {args.model}  repeats={args.repeats}  num_predict={args.num_predict}\n")

    # Warm-up (also forces full load).
    print("Warm-up run (loads model)...")
    run_once(args.model, prompt, args.num_predict)
    residency = ollama_ps()
    print("ollama ps (want 100% GPU on A100):\n" + residency + "\n")

    runs = []
    for i in range(args.repeats):
        r = run_once(args.model, prompt, args.num_predict)
        runs.append(r)
        print(f"  run {i+1}: {r['decode_tok_s']} tok/s decode, "
              f"{r['prompt_eval_tok_s']} tok/s prefill, wall {r['wall_s']}s")

    decode = sorted(x["decode_tok_s"] for x in runs)
    median = decode[len(decode) // 2]
    summary = {
        "tier": "T2",
        "gpu": gpu_info(),
        "model": args.model,
        "ollama_ps": residency,
        "num_predict": args.num_predict,
        "repeats": args.repeats,
        "decode_tok_s_median": median,
        "decode_tok_s_min": decode[0],
        "decode_tok_s_max": decode[-1],
        "runs": runs,
        "note": ("T0 baseline was ~17.7 tok/s at a 45/55 CPU/GPU split; "
                 "A100 should be fully on GPU and much faster."),
    }
    path = OUT / "benchmark_decode_summary.json"
    path.write_text(json.dumps(summary, indent=2))
    print(f"\nMedian decode: {median} tok/s")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
