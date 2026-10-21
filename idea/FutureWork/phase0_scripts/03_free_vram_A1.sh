#!/usr/bin/env bash
# 03_free_vram_A1.sh — Phase 0 item A1 (ADVISORY / guided).
# Goal: free the ~2.9 GB of VRAM your desktop uses so the 9B fits 100% on GPU.
# This script does NOT change your display configuration automatically, because
# switching which GPU drives the display can log you out. It diagnoses, prints
# the exact options for YOUR setup, and verifies the result.
set -euo pipefail
OUT="$(cd "$(dirname "$0")" && pwd)/out"; mkdir -p "$OUT"

echo "=== A1: free dGPU VRAM so the 9B fits fully on GPU ==="
echo

echo "Current VRAM:"
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv 2>/dev/null || true
echo
echo "Desktop/graphics processes on the dGPU (these are the VRAM you want to free):"
nvidia-smi 2>/dev/null | sed -n '/Processes:/,$p'
echo

# Detect an Intel/AMD iGPU to move the display onto.
echo "--- Integrated GPU present? ---"
if command -v lspci >/dev/null 2>&1; then
  lspci | grep -iE "vga|3d|display" || true
fi
echo

SESSION="${XDG_SESSION_TYPE:-unknown}"
echo "Session type: $SESSION"
echo
cat <<EOF
OPTIONS (pick ONE; A is the cleanest on a laptop with an iGPU):

(A) Drive the display from the iGPU, leave the RTX 4060 free for compute.
    - Easiest if your laptop has an Intel/AMD iGPU (most do).
    - BIOS: set primary display to iGPU/Integrated, OR configure PRIME so the
      desktop renders on the iGPU. On KDE/Wayland you typically:
        * Ensure the external/internal panel is wired to the iGPU, then
        * Reboot. The RTX then shows ~0 MiB used until you run compute.
    - Verify: after reboot, 'nvidia-smi' should show NO kwin/plasmashell/
      firefox processes and <300 MiB used.

(B) Keep the dGPU for display but trim the heavy VRAM users before a run.
    - Close Firefox, Telegram, Steam, and other GPU-accelerated apps.
    - This is a stop-gap; it frees ~0.8-1.5 GB, often not enough for a full fit.

(C) Use a smaller / more quantized model so it fits in the free VRAM you have.
    - You already have 'hf.co/unsloth/Qwen3.5-9B-GGUF:Q3_K_M' (5.6 GB) and
      'qwen3.5:4b' (3.4 GB). A Q3 9B or the 4B can fit in ~5 GB free VRAM.
    - Tradeoff: Q3 loses some quality vs Q4; the 4B is faster but weaker.
    - This is config, not display surgery. If you choose this, set demo2 to the
      chosen tag and re-run 04_measure_gpu_fit.sh with that tag.

After doing (A) or (B), RE-RUN:  bash 01_diagnose.sh
Then measure the fit:           bash 04_measure_gpu_fit.sh
EOF

echo
echo "(No changes were made by this script.)"
