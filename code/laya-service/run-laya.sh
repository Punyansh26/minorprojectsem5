#!/usr/bin/env bash
# Start the isolated Laya System 1 service (laya-serve) for Demo 2 routing.
#
# This runs in its OWN virtual environment (code/laya-service/.venv) with its own
# transformers 5.x, so the shared "minor" conda model stack (faster-whisper, Coqui
# TTS, sentence-transformers) is never touched. The agent reaches this service over
# the Jev-compatible POST /v1/systemone wire protocol.
#
# Usage:
#   bash run-laya.sh                 # preload english + multilingual on CPU, port 8077
#   LAYA_PORT=8099 bash run-laya.sh  # override the port
#
# Then in demo2/.env set JEV_ROUTING_MODE=laya (and LAYA_BASE_URL if you changed the
# port), and restart Demo 2.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Keep the ~2.3 GB checkpoints beside the service rather than in the user HF cache.
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HERE/models}"

# CPU inference by default, to reserve GPU memory for local reasoning (Ollama),
# matching Demo 2's device discipline. Set LAYA_DEVICE=cuda to override.
export LAYA_HOST="${LAYA_HOST:-127.0.0.1}"
export LAYA_PORT="${LAYA_PORT:-8077}"
export LAYA_DEVICE="${LAYA_DEVICE:-cpu}"
export LAYA_PRELOAD="${LAYA_PRELOAD:-1}"
# Preload both checkpoints so Hindi (multilingual) and English route with no reload.
export LAYA_MODELS="${LAYA_MODELS:-english,multilingual}"
# Cap CPU threads so routing never starves the rest of the demo.
export LAYA_THREADS="${LAYA_THREADS:-4}"

echo "laya-serve on http://$LAYA_HOST:$LAYA_PORT  (device=$LAYA_DEVICE, models=$LAYA_MODELS)"
echo "checkpoints cache: $HF_HUB_CACHE"
exec "$HERE/.venv/bin/laya-serve"
