#!/usr/bin/env bash
# 02_ollama_keepalive_A3.sh — Phase 0 item A3.
# Keeps the model resident so you don't pay the ~8.3 s cold reload between turns.
# Sets OLLAMA_KEEP_ALIVE=-1 (never unload) via the ollama systemd user/service
# override, or prints manual instructions if ollama is not a systemd service.
#
# Usage:
#   bash 02_ollama_keepalive_A3.sh           # apply
#   bash 02_ollama_keepalive_A3.sh --revert  # undo
set -euo pipefail

REVERT=0
[ "${1:-}" = "--revert" ] && REVERT=1

OUT="$(cd "$(dirname "$0")" && pwd)/out"; mkdir -p "$OUT"

# Detect how ollama runs.
SERVICE=""
if systemctl list-unit-files 2>/dev/null | grep -q '^ollama.service'; then
  SERVICE="system"
elif systemctl --user list-unit-files 2>/dev/null | grep -q '^ollama.service'; then
  SERVICE="user"
fi

apply_systemd () {
  local scope="$1"   # system | user
  local sctl="systemctl"; local dropin_dir="/etc/systemd/system/ollama.service.d"
  local sudo_cmd="sudo"
  if [ "$scope" = "user" ]; then
    sctl="systemctl --user"; dropin_dir="$HOME/.config/systemd/user/ollama.service.d"; sudo_cmd=""
  fi
  echo "Ollama runs as a $scope systemd service. Writing keep-alive override."
  $sudo_cmd mkdir -p "$dropin_dir"
  $sudo_cmd tee "$dropin_dir/keepalive.conf" >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_KEEP_ALIVE=-1"
EOF
  echo "Wrote $dropin_dir/keepalive.conf"
  if [ "$scope" = "user" ]; then
    systemctl --user daemon-reload; systemctl --user restart ollama
  else
    sudo systemctl daemon-reload; sudo systemctl restart ollama
  fi
  echo "Restarted ollama ($scope)."
}

revert_systemd () {
  local scope="$1"; local dropin="/etc/systemd/system/ollama.service.d/keepalive.conf"; local sudo_cmd="sudo"
  [ "$scope" = "user" ] && { dropin="$HOME/.config/systemd/user/ollama.service.d/keepalive.conf"; sudo_cmd=""; }
  $sudo_cmd rm -f "$dropin" && echo "Removed $dropin"
  if [ "$scope" = "user" ]; then systemctl --user daemon-reload; systemctl --user restart ollama
  else sudo systemctl daemon-reload; sudo systemctl restart ollama; fi
  echo "Reverted keep-alive ($scope)."
}

if [ "$REVERT" -eq 1 ]; then
  if [ -n "$SERVICE" ]; then revert_systemd "$SERVICE"
  else
    echo "Ollama is not a systemd service here. To revert manually, remove"
    echo "OLLAMA_KEEP_ALIVE from your shell profile / launch command."
  fi
  exit 0
fi

if [ -n "$SERVICE" ]; then
  apply_systemd "$SERVICE"
else
  cat <<'EOF'
Ollama is NOT managed by systemd on this machine (you likely start it manually
with `ollama serve`). Apply A3 by exporting the variable before starting it:

    export OLLAMA_KEEP_ALIVE=-1
    ollama serve

To make it permanent, add that export line to ~/.bashrc or ~/.zshrc.
(-1 = never unload. For a kiosk this is what you want. Use e.g. "30m" if you
prefer a timeout.)
EOF
fi

echo
echo "Verify after applying:"
echo "  OLLAMA_KEEP_ALIVE should be -1; after one query, 'ollama ps' should show UNTIL = Forever."
