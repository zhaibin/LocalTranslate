#!/usr/bin/env bash
set -euo pipefail

LABEL="com.local.translate-service"
REMOVE_VENV=0

usage() {
  cat <<'EOF'
Usage: scripts/uninstall_macos.sh [options]

Options:
  --remove-venv           Remove the project .venv after unloading the service.
  --help                  Print this help.

By default this uninstaller removes only the user LaunchAgent plist.
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

[ "$(uname -s)" = "Darwin" ] || die "This uninstaller only supports macOS."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.local.translate-service.plist"

log "Unloading $LABEL LaunchAgent if it is loaded."
launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true

if [ -f "$PLIST_PATH" ]; then
  rm -f "$PLIST_PATH"
  log "Removed $PLIST_PATH"
else
  log "No LaunchAgent plist found at $PLIST_PATH"
fi

if [ "$REMOVE_VENV" -eq 1 ]; then
  rm -rf "$PROJECT_ROOT/.venv"
  log "Removed $PROJECT_ROOT/.venv"
else
  log "Kept project .venv. Rerun with --remove-venv to remove it."
fi

log "Uninstall complete."
log "Kept project source, Ollama, Ollama models, and logs."
log "Logs remain in $HOME/Library/Logs/translate-service if they existed."
