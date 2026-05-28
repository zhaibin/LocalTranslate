#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="translate-service.service"
REMOVE_VENV=0

usage() {
  cat <<'EOF'
Usage: scripts/uninstall_linux.sh [options]

Options:
  --remove-venv           Remove the project .venv after stopping the user service.
  --help                  Print this help.

By default this uninstaller removes only the user systemd service file.
It keeps the project source, Ollama, Ollama models, project .venv, and logs.
EOF
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --remove-venv) REMOVE_VENV=1; shift ;;
    --help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[ "$(uname -s)" = "Linux" ] || die "This uninstaller only supports Linux."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
SERVICE_PATH="$HOME/.config/systemd/user/translate-service.service"

if command -v systemctl >/dev/null 2>&1; then
  log "Stopping $SERVICE_NAME user service if it is loaded."
  systemctl --user disable --now translate-service.service >/dev/null 2>&1 || true
else
  log "systemctl is not available; skipping service stop."
fi

if [ -f "$SERVICE_PATH" ]; then
  rm -f "$SERVICE_PATH"
  log "Removed $SERVICE_PATH"
else
  log "No user systemd service found at $SERVICE_PATH"
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

if [ "$REMOVE_VENV" -eq 1 ]; then
  rm -rf "$PROJECT_ROOT/.venv"
  log "Removed $PROJECT_ROOT/.venv"
else
  log "Kept project .venv. Rerun with --remove-venv to remove it."
fi

log "Uninstall complete."
log "Kept project source, Ollama, Ollama models, and logs."
log "Logs remain available from journalctl --user -u translate-service.service if journald retained them."
