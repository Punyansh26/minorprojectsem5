#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec conda run --no-capture-output -n minor python -m streamlit run app.py "$@"
