#!/usr/bin/env bash
# Runner for the chapter-03 long tests. Resumable: skips a test whose summary.json
# already exists unless --force. --check runs only fast validation (no downloads,
# no model loads, no long runs).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK=0; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --force) FORCE=1 ;;
    *) echo "unknown arg: $arg"; exit 2 ;;
  esac
done

run_one() {
  local id="$1"; local script="$2"; local outdir="$HERE/$3"
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

run_one L0 l0_streaming_residual.py L0_streaming
run_one L1 l1_eou_sweep.py          L1_eou
run_one L2 l2_mms_latency.py        L2_mms
echo "All long tests finished. Summaries:"
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
