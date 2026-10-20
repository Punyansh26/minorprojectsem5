#!/usr/bin/env bash
# Runner for the chapter-02 long tests. Resumable: skips a test whose summary.json
# already exists unless --force is given. --check runs only fast validation.
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
  python "$HERE/$script" --out "$outdir/summary.json"
  echo "=== $id done -> $outdir/summary.json ==="
}

run_one L1 l1_decode_rates.py L1_rates
run_one L0 l0_energy_per_turn.py L0_energy
echo "All long tests finished. Summaries:"
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
