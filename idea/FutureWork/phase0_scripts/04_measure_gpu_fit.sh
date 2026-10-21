#!/usr/bin/env bash
# 04_measure_gpu_fit.sh — verify the 9B loads 100% on GPU and measure decode tok/s.
# Run this when the GPU is otherwise idle. It loads the model, runs one short
# generation, reads the CPU/GPU split from `ollama ps`, and unloads.
#
# Usage: bash 04_measure_gpu_fit.sh [MODEL_TAG]
#   default MODEL_TAG = qwen3.5:9b
set -euo pipefail
MODEL="${1:-qwen3.5:9b}"
OUT="$(cd "$(dirname "$0")" && pwd)/out"; mkdir -p "$OUT"
REPORT="$OUT/04_gpu_fit_${MODEL//[^a-zA-Z0-9]/_}.txt"

command -v ollama >/dev/null 2>&1 || { echo "ollama not found"; exit 1; }

{
  echo "=== GPU-fit + decode measurement for '$MODEL' @ $(date -Is) ==="
  echo
  echo "Free VRAM before load:"
  nvidia-smi --query-gpu=memory.free --format=csv,noheader 2>/dev/null || true
  echo

  echo "Warming the model (loads it into memory)..."
  ollama run "$MODEL" "Reply with the single word: ready" >/dev/null 2>&1 || {
    echo "Model failed to run. Is '$MODEL' pulled? Try: ollama list"; exit 1; }

  echo
  echo "Residency split (PROCESSOR column: 100% GPU is the target for A1):"
  ollama ps 2>/dev/null | tee -a "$REPORT" || true
  echo
  echo "VRAM in use now:"
  nvidia-smi --query-gpu=memory.used,memory.free --format=csv 2>/dev/null || true
  echo

  echo "Decode-speed probe (eval tok/s from --verbose):"
  # ollama prints eval rate on stderr with --verbose
  PROMPT="List three fruits, one word each, no extra text."
  { ollama run --verbose "$MODEL" "$PROMPT" 2>&1 1>/dev/null | grep -iE "eval rate|eval count|total duration"; } \
    | tee -a "$REPORT" || echo "(could not capture eval rate; your ollama version may format differently)"
  echo

  echo "Unloading the model (keep_alive 0 for this probe)..."
  OLLAMA_KEEP_ALIVE=0 ollama stop "$MODEL" 2>/dev/null || ollama run "$MODEL" --keepalive 0 "" >/dev/null 2>&1 || true
  echo
  echo "Interpretation:"
  echo "  - 'ollama ps' PROCESSOR = '100% GPU'  -> A1 succeeded (fully on GPU)."
  echo "  - If it shows e.g. '48%/52% CPU/GPU'  -> still spilling; free more VRAM (03) or use a smaller tag."
  echo "  - Baseline on this laptop was ~17.7 tok/s at a 45/55 CPU/GPU split; target ~32 tok/s fully on GPU."
  echo "=== end ==="
} | tee "$REPORT"

echo
echo "Saved to: $REPORT"
