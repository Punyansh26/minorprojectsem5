#!/usr/bin/env bash
# Runner for the chapter-09 long tests. Resumable: skips a test whose summary.json
# already exists unless --force. --check runs only fast validation (no downloads,
# no model loads, no long runs) and is what the agent used to syntax/paths-verify.
#
# L0 is Demo2-local and CPU-only (no download); L1/L2/L3 download encoder/LLM weights
# and train on the GPU. On the 8 GB T0, run L3 (QLoRA drafter) with Ollama stopped.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
    python "$HERE/$script" --check --out "$outdir/summary.json"
    return
  fi
  if [[ -f "$outdir/summary.json" && "$FORCE" == 0 ]]; then
    echo "$id: summary.json exists, skipping (use --force to re-run)"; return
  fi
  echo "=== $id starting ==="
  python "$HERE/$script" --out "$outdir/summary.json" || echo "$id: FAILED (see output)"
  echo "=== $id done -> $outdir/summary.json ==="
}

run_one L0 l0_build_triple_store.py   L0_triple_store
run_one L1 l1_encoder_verifier.py     L1_verifier
run_one L2 l2_multilingual_router.py  L2_router
run_one L3 l3_lora_drafter.py         L3_drafter
echo "All requested long tests finished. Summaries:"
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
