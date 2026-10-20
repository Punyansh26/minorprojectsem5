#!/usr/bin/env bash
# Chapter-04 long tests. Resumable: a test with an existing summary.json is skipped unless --force.
# --check runs only fast validation (no download, no model load).
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
  local id="$1" script="$2" outdir="$HERE/$3"
  mkdir -p "$outdir"
  if [[ "$CHECK" == 1 ]]; then
    python "$HERE/$script" --check --out "$outdir/check.json"; return
  fi
  if [[ -f "$outdir/summary.json" && "$FORCE" == 0 ]]; then
    echo "$id: summary.json exists, skipping (use --force)"; return
  fi
  echo "=== $id starting ==="
  python "$HERE/$script" --out "$outdir/summary.json"
  echo "=== $id done -> $outdir/summary.json ==="
}

run_one L0 l0_fetch_reranker.py L0_fetch
run_one L1 l1_rerank_ab.py      L1_rerank_ab
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
