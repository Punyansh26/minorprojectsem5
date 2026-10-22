#!/usr/bin/env bash
# colab_go.sh -- run on your LAPTOP (not in Colab).
#
# One command does everything:
#   1. makes sure the A100 session exists (creates it if missing)
#   2. uploads colab.env (your keys) to the VM as /content/.env
#   3. runs run_all.py on the VM (all stages)
#   4. downloads every result file into this RTX folder
#
# Usage:   bash colab_go.sh
# Options: COLAB_SESSION=name bash colab_go.sh   (default session: minor)
set -uo pipefail

# Resolve this script's own folder, so paths with spaces never need typing.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${COLAB_SESSION:-minor}"
LOG="$HERE/colab_run_latest.log"

# Find the colab CLI even when this script runs without your shell's PATH.
if ! command -v colab >/dev/null 2>&1; then
  for d in "$HOME/miniconda3/bin" "$HOME/anaconda3/bin" "$HOME/.local/bin"; do
    [ -x "$d/colab" ] && export PATH="$d:$PATH" && break
  done
fi
command -v colab >/dev/null 2>&1 || { echo "[go] colab CLI not found (install: uv tool install google-colab-cli)"; exit 1; }

echo "[go] session: $SESSION"
echo "[go] results folder: $HERE"

# 1. Session (create an A100 one if it isn't there).
if ! colab status -s "$SESSION" 2>/dev/null | grep -q "A100"; then
  echo "[go] session '$SESSION' missing or not A100 -> creating it"
  colab new -s "$SESSION" --gpu A100 || { echo "[go] could not create session"; exit 1; }
fi

# 2. Keys / settings.
if [ -f "$HERE/colab.env" ]; then
  colab upload -s "$SESSION" "$HERE/colab.env" /content/.env \
    || echo "[go] WARNING: colab.env upload failed; continuing with defaults"
fi

# 3. Run the pipeline; keep a copy of the full output locally.
colab exec -s "$SESSION" -f "$HERE/run_all.py" 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}

# 4. Download results (missing files are skipped, e.g. if a stage didn't run).
echo
echo "[go] downloading results into $HERE"
for f in benchmark_decode_summary.json demo2_latency_summary.json demo2_latency_groq_summary.json ollama.log; do
  if colab download -s "$SESSION" "/content/colab_out/$f" "$HERE/$f" >/dev/null 2>&1; then
    echo "  saved  $f"
  else
    echo "  skip   $f (not on VM)"
  fi
done
echo "  saved  colab_run_latest.log (full console output)"

exit "$RC"
