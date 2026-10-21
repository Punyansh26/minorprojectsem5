#!/usr/bin/env bash
# FutureWork 11 long-test runner. Runs the fast regression (L1) now and prints how to run the
# GPU/human-dependent L0. Resumable: each test writes its own summary.json; re-running is safe.
# Scratch state stays under $TMPDIR (never code/demo2/data/). No model is loaded by L1.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY="${PYTHON:-python}"   # expects the `minor` env on PATH (conda activate minor)
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/fw11_long.XXXXXX")"
echo "Scratch dir: $SCRATCH"

echo "==> L1: fast fact-leakage regression on shipped fillers"
"$PY" measure_fact_leakage.py --out "$SCRATCH/L1"
L1_STATUS=$?
echo "L1 summary: $SCRATCH/L1/summary.json (exit $L1_STATUS)"

echo
echo "==> L0: audio-logged 120-turn talker fact-leakage (manual input required)"
echo "   1) Produce a talker transcript (one utterance per line) from the 120-turn benchmark"
echo "      talker/acknowledgement audio, e.g. talker_track_120.txt"
echo "   2) Run:"
echo "      $PY measure_fact_leakage.py --transcript talker_track_120.txt --out \"$SCRATCH/L0\""
echo "   3) Pass criterion: summary.json -> pass==true (rate==0.0). Any leak fails."
echo
echo "Done. Hand back: $SCRATCH/L1/summary.json (and $SCRATCH/L0/summary.json once L0 is run)."
