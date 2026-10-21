#!/usr/bin/env bash
# Runner for the chapter-12 long tests. Resumable: skips a test whose summary.json already
# exists unless --force. --check runs only fast validation (no downloads, no model loads, no
# long runs) and is what the agent used to syntax/paths-verify.
#
# All tests target Demo2 and write their scratch + summary.json UNDER THIS DIRECTORY, never
# into code/demo2/data. Where a test loads a model it unloads it (ollama stop / del) at the end.
#
#   L0  ASR WER/CER (jiwer)          needs: recorded speech set + faster-whisper (download once)
#   L1  TTS MOS + round-trip CER     needs: UTMOS/SpeechMOS (torch.hub download) + number set
#   L2  claim audit (local checker)  needs: a local checker model + >=300 clean cases + GPU
#   L3  tool task runner (pass^k)    needs: Demo2 agent + Ollama idle on the GPU
#   L4  energy per turn              needs: GPU idle + nvidia-smi + RAPL; samples a real run
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python}"
CHECK=0; FORCE=0; ONLY=""
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --force) FORCE=1 ;;
    --only=*) ONLY="${arg#*=}" ;;
    *) echo "unknown arg: $arg"; exit 2 ;;
  esac
done

run_one() {
  local id="$1"; local script="$2"; local outdir="$HERE/$3"
  if [[ -n "$ONLY" && "$ONLY" != "$id" ]]; then return; fi
  mkdir -p "$outdir"
  if [[ "$CHECK" == 1 ]]; then
    "$PY" "$HERE/$script" --check --out "$outdir/summary.json"
    return
  fi
  if [[ -f "$outdir/summary.json" && "$FORCE" == 0 ]]; then
    echo "$id: summary.json exists, skipping (use --force to re-run)"; return
  fi
  echo "=== $id starting ==="
  "$PY" "$HERE/$script" --out "$outdir/summary.json" || echo "$id: FAILED (see output)"
  echo "=== $id done -> $outdir/summary.json ==="
}

run_one L0 l0_asr_wer.py       L0_asr_wer
run_one L1 l1_tts_mos.py       L1_tts_mos
run_one L2 l2_claim_audit.py   L2_claim_audit
run_one L3 l3_tool_tasks.py    L3_tool_tasks
run_one L4 l4_energy.py        L4_energy
echo "All requested long tests finished. Summaries:"
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
