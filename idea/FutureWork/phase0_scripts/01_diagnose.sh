#!/usr/bin/env bash
# 01_diagnose.sh — Phase 0 read-only diagnosis. Changes nothing.
# Reports GPU/VRAM, display co-tenants, Ollama state, and model sizes
# so you know how much VRAM A1 must free before the 9B can fit fully on GPU.
# Informational only: do NOT use 'set -e' here, or an empty query aborts the run.
set -uo pipefail
true  # ensure the script never exits early on a non-zero informational command
OUT="$(cd "$(dirname "$0")" && pwd)/out"
mkdir -p "$OUT"
REPORT="$OUT/01_diagnose.txt"

{
  echo "=== Phase 0 diagnosis @ $(date -Is) ==="
  echo

  echo "--- GPU (nvidia-smi) ---"
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
      --format=csv 2>/dev/null || nvidia-smi
    echo
    echo "Processes holding VRAM (these are what A1 wants to move off the dGPU):"
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null || true
    # Graphics apps are not always shown by the query above; show the table too (capped):
    { nvidia-smi 2>/dev/null | sed -n '/Processes:/,$p' | head -20; } || true
  else
    echo "nvidia-smi NOT FOUND — no NVIDIA driver visible."
  fi
  echo

  echo "--- Free VRAM estimate ---"
  if command -v nvidia-smi >/dev/null 2>&1; then
    FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
    echo "Free VRAM: ${FREE} MiB"
    echo "qwen3.5:9b is ~6.6 GB (~6758 MiB). It needs that PLUS KV-cache headroom."
    if [ -n "${FREE:-}" ] && [ "${FREE}" -lt 7000 ] 2>/dev/null; then
      echo ">> Less than ~7000 MiB free: the 9B will SPILL to CPU. A1 (03_free_vram_A1.sh) is needed."
    else
      echo ">> Looks like enough free VRAM for a full-GPU load. Verify with 04_measure_gpu_fit.sh."
    fi
  fi
  echo

  echo "--- Display server ---"
  echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-unknown}  (wayland vs x11 changes how A1 is done)"
  echo

  echo "--- Ollama ---"
  if command -v ollama >/dev/null 2>&1; then
    ollama --version 2>/dev/null || true
    echo "KEEP_ALIVE env currently: OLLAMA_KEEP_ALIVE=${OLLAMA_KEEP_ALIVE:-<unset>}"
    echo "Models:"
    ollama list 2>/dev/null || echo "  (cannot list — is 'ollama serve' running?)"
    echo "Resident now (ollama ps):"
    ollama ps 2>/dev/null || true
  else
    echo "ollama NOT FOUND."
  fi
  echo

  echo "--- Which model does demo2 expect? (read-only grep) ---"
  REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
  if [ -d "$REPO_ROOT/code/demo2" ]; then
    grep -RniE "qwen3|ollama_model|model.*=.*qwen|OLLAMA_MODEL" \
      "$REPO_ROOT/code/demo2" 2>/dev/null | grep -vi test | head -20 \
      || echo "  (no obvious model pin found in code/demo2)"
  else
    echo "  code/demo2 not found at $REPO_ROOT/code/demo2"
  fi
  echo
  echo "=== end diagnosis ==="
} | tee "$REPORT"

echo
echo "Saved to: $REPORT"
