#!/usr/bin/env bash
set -euo pipefail

LABEL="com.local.translate-service"
INSTALL_SERVICE=0
INSTALL_OLLAMA=0
PULL_MODEL=1
HOST="127.0.0.1"
PORT="8000"
MODEL="translategemma:latest"
SOURCE_LANG="en"
TARGET_LANG="zh"
OLLAMA_BASE_URL="http://127.0.0.1:11434"
REQUEST_TIMEOUT_SECONDS="120"

usage() {
  cat <<'EOF'
Usage: scripts/install_macos.sh [options]

Options:
  --install-service       Install and start the user LaunchAgent HTTP service.
  --install-ollama        If Ollama is missing, try to install it with Homebrew.
  --pull-model            Pull/update the configured Ollama model. Default.
  --no-pull-model         Skip model pull.
  --host HOST             HTTP service host. Default: 127.0.0.1.
  --port PORT             HTTP service port. Default: 8000.
  --model MODEL           Ollama model. Default: translategemma:latest.
  --source-lang CODE      Default source language. Default: en.
  --target-lang CODE      Default target language. Default: zh.
  --ollama-base-url URL   Ollama API URL. Default: http://127.0.0.1:11434.
  --help                  Print this help.
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
    --install-service) INSTALL_SERVICE=1; shift ;;
    --install-ollama) INSTALL_OLLAMA=1; shift ;;
    --pull-model) PULL_MODEL=1; shift ;;
    --no-pull-model) PULL_MODEL=0; shift ;;
    --host) HOST="${2:-}"; [ -n "$HOST" ] || die "--host requires a value"; shift 2 ;;
    --port) PORT="${2:-}"; [ -n "$PORT" ] || die "--port requires a value"; shift 2 ;;
    --model) MODEL="${2:-}"; [ -n "$MODEL" ] || die "--model requires a value"; shift 2 ;;
    --source-lang) SOURCE_LANG="${2:-}"; [ -n "$SOURCE_LANG" ] || die "--source-lang requires a value"; shift 2 ;;
    --target-lang) TARGET_LANG="${2:-}"; [ -n "$TARGET_LANG" ] || die "--target-lang requires a value"; shift 2 ;;
    --ollama-base-url) OLLAMA_BASE_URL="${2:-}"; [ -n "$OLLAMA_BASE_URL" ] || die "--ollama-base-url requires a value"; shift 2 ;;
    --help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
VENV_DIR="$PROJECT_ROOT/.venv"
PLIST_PATH="$HOME/Library/LaunchAgents/com.local.translate-service.plist"
LOG_DIR="$HOME/Library/Logs/translate-service"

log "[1/7] Checking macOS and Python"
[ "$(uname -s)" = "Darwin" ] || die "This installer only supports macOS."
[ -f "$PROJECT_ROOT/pyproject.toml" ] || die "Run this script from a valid project checkout."

PYTHON_BIN=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      PYTHON_BIN="$(command -v "$candidate")"
      break
    fi
  fi
done
[ -n "$PYTHON_BIN" ] || die "Python 3.11+ is required."

log "[2/7] Checking Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  if [ "$INSTALL_OLLAMA" -eq 1 ]; then
    command -v brew >/dev/null 2>&1 || die "Homebrew is required for --install-ollama. Install Homebrew or Ollama manually."
    brew install ollama
  else
    die "Ollama is not installed. Install it manually or rerun with --install-ollama."
  fi
fi

log "[3/7] Creating virtual environment"
"$PYTHON_BIN" -m venv "$VENV_DIR"

log "[4/7] Installing translate-service"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"

log "[5/7] Writing configuration"
cat > "$PROJECT_ROOT/.env" <<EOF
OLLAMA_BASE_URL=$OLLAMA_BASE_URL
OLLAMA_MODEL=$MODEL
DEFAULT_SOURCE_LANG=$SOURCE_LANG
DEFAULT_TARGET_LANG=$TARGET_LANG
REQUEST_TIMEOUT_SECONDS=$REQUEST_TIMEOUT_SECONDS
EOF

if [ "$PULL_MODEL" -eq 1 ]; then
  log "[6/7] Pulling Ollama model $MODEL"
  ollama pull "$MODEL" || die "Failed to pull model $MODEL. Check Ollama and network access."
else
  log "[6/7] Skipping model pull"
fi

if [ "$INSTALL_SERVICE" -eq 1 ]; then
  log "[7/7] Installing LaunchAgent service"
  mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
  cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV_DIR/bin/translate</string>
    <string>serve</string>
    <string>--host</string>
    <string>$HOST</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$PROJECT_ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OLLAMA_BASE_URL</key>
    <string>$OLLAMA_BASE_URL</string>
    <key>OLLAMA_MODEL</key>
    <string>$MODEL</string>
    <key>DEFAULT_SOURCE_LANG</key>
    <string>$SOURCE_LANG</string>
    <key>DEFAULT_TARGET_LANG</key>
    <string>$TARGET_LANG</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/stderr.log</string>
</dict>
</plist>
EOF
  plutil -lint "$PLIST_PATH"
  launchctl bootout gui/$UID "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl bootstrap gui/$UID "$PLIST_PATH" || die "Failed to bootstrap LaunchAgent. Check $PLIST_PATH and logs in $LOG_DIR."
  launchctl kickstart -k gui/$UID/com.local.translate-service || die "Failed to start LaunchAgent. Run: launchctl print gui/$UID/$LABEL"
  sleep 2
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "http://$HOST:$PORT/health" || log "Health check did not return ok. Check logs in $LOG_DIR."
  fi
else
  log "[7/7] Skipping LaunchAgent service"
fi

"$VENV_DIR/bin/translate" --help >/dev/null
log "Install complete."
log "CLI: $VENV_DIR/bin/translate text --from en --to zh \"Hello\""
if [ "$INSTALL_SERVICE" -eq 1 ]; then
  log "HTTP health: curl http://$HOST:$PORT/health"
  log "Logs: $LOG_DIR"
fi
