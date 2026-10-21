#!/usr/bin/env bash
# 01_bootstrap.sh — Colab (Tier T2: A100/A80) bootstrap for the Minor voice stack.
#
# What it does (idempotent, safe to re-run in a fresh Colab session):
#   1. Clones the repo into /content/minor  (token read from env GH_TOKEN, NOT hardcoded)
#   2. Installs demo2 + institute-assistant Python deps
#   3. Installs Ollama and starts it with GPU
#   4. Pulls the reasoning model
#
# IMPORTANT — do NOT hardcode your GitHub token in a notebook. In Colab:
#     from google.colab import userdata
#     os.environ["GH_TOKEN"] = userdata.get("GH_TOKEN")   # store it in the 🔑 Secrets panel
# then run this script. If the repo is public, GH_TOKEN can be empty.
#
# Usage:  bash 01_bootstrap.sh [MODEL_TAG]
#   MODEL_TAG default: qwen3.5:9b   (fits easily on A100; use Q4/Q8 freely on T2)
set -uo pipefail

MODEL="${1:-qwen3.5:9b}"
WORK="/content/minor"
REPO_USER="Punyansh26"
REPO="minorprojectsem5"
BRANCH="${REPO_BRANCH:-main}"
OUT="/content/colab_out"; mkdir -p "$OUT"
LOG="$OUT/bootstrap.log"

say(){ echo -e "\n=== $* ==="; }

say "0. Environment"
echo "Working dir: $WORK"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv 2>/dev/null \
  || echo "WARNING: no GPU visible. In Colab: Runtime > Change runtime type > A100/GPU."

say "1. Clone / update repo"
if [ -d "$WORK/.git" ]; then
  echo "Repo already present; pulling latest."
  git -C "$WORK" pull --ff-only || echo "pull skipped (local changes?)"
else
  if [ -n "${GH_TOKEN:-}" ]; then
    # Token is used only for this clone URL in-memory; it is not written to disk config.
    git clone --branch "$BRANCH" \
      "https://${GH_TOKEN}@github.com/${REPO_USER}/${REPO}.git" "$WORK"
    # Scrub the token out of the stored remote so it isn't saved in .git/config.
    git -C "$WORK" remote set-url origin "https://github.com/${REPO_USER}/${REPO}.git"
  else
    echo "No GH_TOKEN set — trying a public clone."
    git clone --branch "$BRANCH" \
      "https://github.com/${REPO_USER}/${REPO}.git" "$WORK" \
      || { echo "Clone failed. If the repo is private, set GH_TOKEN (see header)."; exit 1; }
  fi
fi
echo "Repo at: $WORK"
ls "$WORK/code/demo2" >/dev/null 2>&1 && echo "demo2 found." || { echo "demo2 missing — wrong branch? (try REPO_BRANCH=code)"; }

say "2. Python dependencies"
# Colab already has torch + CUDA. Install only the demo2 + agent extras.
pip -q install \
  "streamlit==1.49.1" "edge-tts==7.2.8" "soundfile>=0.12" "scipy>=1.11" \
  "python-dotenv>=1.0" "faster-whisper==1.2.1" 2>&1 | tail -3
# institute-assistant supplies the agent/RAG stack demo2 imports.
if [ -f "$WORK/code/Institute-voice-agent/institute-assistant/requirements.txt" ]; then
  pip -q install -r "$WORK/code/Institute-voice-agent/institute-assistant/requirements.txt" 2>&1 | tail -5 || true
fi

say "3. Install + start Ollama (GPU)"
if ! command -v ollama >/dev/null 2>&1; then
  # The Ollama installer needs zstd to unpack; Colab images often lack it.
  if ! command -v zstd >/dev/null 2>&1; then
    echo "Installing zstd (required by the Ollama installer)..."
    (sudo apt-get -qq update && sudo apt-get -qq install -y zstd) 2>/dev/null \
      || apt-get -qq install -y zstd 2>/dev/null \
      || echo "WARNING: could not install zstd automatically; run 'apt-get install -y zstd'."
  fi
  curl -fsSL https://ollama.com/install.sh | sh
fi
command -v ollama >/dev/null 2>&1 || { echo "Ollama install failed (is zstd present?). Fix and re-run."; exit 1; }
# A3 (keep-alive) still applies on T2: keep the model resident across turns.
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}"
export OLLAMA_HOST="127.0.0.1:11434"
# Start the server in the background (no systemd in Colab).
if ! curl -s "http://127.0.0.1:11434/api/version" >/dev/null 2>&1; then
  echo "Starting ollama serve (log: $OUT/ollama.log)..."
  nohup ollama serve > "$OUT/ollama.log" 2>&1 &
  for i in $(seq 1 30); do
    curl -s "http://127.0.0.1:11434/api/version" >/dev/null 2>&1 && break
    sleep 1
  done
fi
curl -s "http://127.0.0.1:11434/api/version" && echo "  <- ollama up" || echo "ollama did NOT start; see $OUT/ollama.log"

say "4. Pull model: $MODEL"
ollama pull "$MODEL" 2>&1 | tail -3

say "Done. Next: bash 02_serve_config.sh   then   bash 03_benchmark_decode.sh"
echo "Repo:  $WORK"
echo "Env for demo2:  export DEMO2_CODE_ROOT=$WORK/code ; export OLLAMA_MODEL=$MODEL"
