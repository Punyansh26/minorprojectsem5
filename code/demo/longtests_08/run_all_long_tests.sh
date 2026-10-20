#!/usr/bin/env bash
# Run the Task 08 long tests. L0 and L2 are local; L1 needs GROQ_API_KEY (pass --live).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/.."                      # run from code/demo
mkdir -p "$HERE/out"

echo "== L0: tool-selection accuracy vs schema cost (local) =="
python "$HERE/L0_tool_selection.py" || echo "L0 did not meet pass criterion (see out/L0/summary.json)"

echo "== L2: injection / safety red team (local) =="
python "$HERE/L2_injection_redteam.py" || echo "L2 FAILED (see out/L2/summary.json)"

if [[ "${1:-}" == "--live" ]]; then
  echo "== L1: live-Groq fast-path A/B (needs GROQ_API_KEY) =="
  python "$HERE/L1_live_fastpath_ab.py" || echo "L1 did not meet pass criterion (see out/L1/summary.json)"
else
  echo "== L1 skipped (pass --live with GROQ_API_KEY to run) =="
fi

echo "Summaries written under $HERE/out/<id>/summary.json"
