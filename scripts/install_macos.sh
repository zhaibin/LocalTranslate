#!/usr/bin/env bash
set -euo pipefail

LABEL="com.local.translate-service"
DEFAULT_OLLAMA_BASE_URL="http://127.0.0.1:11434"
INSTALL_SERVICE=0
INSTALL_OLLAMA=0
PULL_MODEL=1
HOST="127.0.0.1"
PORT="8000"
MODEL="translategemma:latest"
SOURCE_LANG="en"
TARGET_LANG="zh"
OLLAMA_BASE_URL="$DEFAULT_OLLAMA_BASE_URL"
REQUEST_TIMEOUT_SECONDS="120"
OLLAMA_READY_TIMEOUT_SECONDS=30

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
ENV_PATH="$PROJECT_ROOT/.env"
PLIST_PATH="$HOME/Library/LaunchAgents/com.local.translate-service.plist"
LOG_DIR="$HOME/Library/Logs/translate-service"

validate_no_newline() {
  name="$1"
  value="$2"
  case "$value" in
    *$'\n'*|*$'\r'*)
      die "$name must not contain literal newlines."
      ;;
  esac
}

validate_dotenv_token() {
  name="$1"
  value="$2"
  validate_no_newline "$name" "$value"
  case "$value" in
    ""|*[[:space:]]*|*"#"*|*"'"*|*'"'*)
      die "$name must not be empty or contain whitespace, #, or quotes."
      ;;
  esac
}

validate_lang_code() {
  name="$1"
  value="$2"
  validate_no_newline "$name" "$value"
  case "$value" in
    ""|*[!A-Za-z0-9-]*)
      die "$name must contain only BCP47 language-code characters: A-Z, a-z, 0-9, or '-'."
      ;;
  esac
}

validate_port() {
  port="$1"
  case "$port" in
    ""|*[!0-9]*)
      die "--port must be numeric."
      ;;
    0|0*)
      die "--port must be between 1 and 65535."
      ;;
  esac
  port_num=$((10#$port))
  if ((port_num < 1 || port_num > 65535)); then
    die "--port must be between 1 and 65535."
  fi
}

wait_for_ollama() {
  command -v curl >/dev/null 2>&1 || return 2

  elapsed=0
  while [ "$elapsed" -lt "$OLLAMA_READY_TIMEOUT_SECONDS" ]; do
    if curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_BASE_URL/api/tags" >/dev/null; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

start_local_ollama() {
  log "Starting local Ollama"
  mkdir -p "$LOG_DIR"
  if command -v brew >/dev/null 2>&1 && brew services list >/dev/null 2>&1; then
    brew services start ollama || log "brew services could not start Ollama; trying ollama serve."
    if wait_for_ollama; then
      return 0
    fi
  fi

  ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
}

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
    if [ "$OLLAMA_BASE_URL" = "$DEFAULT_OLLAMA_BASE_URL" ]; then
      start_local_ollama
    fi
  else
    die "Ollama is not installed. Install it manually or rerun with --install-ollama."
  fi
fi
if command -v curl >/dev/null 2>&1; then
  if ! wait_for_ollama; then
    if [ "$INSTALL_OLLAMA" -eq 1 ] && [ "$OLLAMA_BASE_URL" = "$DEFAULT_OLLAMA_BASE_URL" ]; then
      start_local_ollama
      wait_for_ollama || die "Ollama HTTP API is not reachable at $OLLAMA_BASE_URL. Installed Ollama is not ready. Please start Ollama first, or run 'ollama serve', and rerun the installer."
    else
      die "Ollama HTTP API is not reachable at $OLLAMA_BASE_URL. Installed Ollama is not ready. Please start Ollama first, or run 'ollama serve', and rerun the installer."
    fi
  fi
else
  log "curl is not available; skipping Ollama HTTP API readiness check."
fi

log "[3/7] Creating virtual environment"
"$PYTHON_BIN" -m venv "$VENV_DIR"

log "[4/7] Installing translate-service"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"

log "[5/7] Writing configuration"
validate_dotenv_token "OLLAMA_BASE_URL" "$OLLAMA_BASE_URL"
validate_dotenv_token "OLLAMA_MODEL" "$MODEL"
validate_lang_code "DEFAULT_SOURCE_LANG" "$SOURCE_LANG"
validate_lang_code "DEFAULT_TARGET_LANG" "$TARGET_LANG"
validate_no_newline "REQUEST_TIMEOUT_SECONDS" "$REQUEST_TIMEOUT_SECONDS"
if [ -f "$ENV_PATH" ]; then
  ENV_BACKUP_PATH="$PROJECT_ROOT/.env.backup.$(date +%Y%m%d%H%M%S)"
  cp "$ENV_PATH" "$ENV_BACKUP_PATH"
  log "Backed up existing .env to $ENV_BACKUP_PATH"
fi
cat > "$ENV_PATH" <<EOF
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
  validate_port "$PORT"
  "$VENV_DIR/bin/python" - "$PLIST_PATH" "$LABEL" "$VENV_DIR/bin/translate" "$HOST" "$PORT" "$PROJECT_ROOT" "$OLLAMA_BASE_URL" "$MODEL" "$SOURCE_LANG" "$TARGET_LANG" "$LOG_DIR" <<'PY'
import plistlib
import sys
from pathlib import Path

(
    plist_path,
    label,
    translate_bin,
    host,
    port,
    project_root,
    ollama_base_url,
    model,
    source_lang,
    target_lang,
    log_dir,
) = sys.argv[1:]

plist = {
    "Label": label,
    "ProgramArguments": [
        translate_bin,
        "serve",
        "--host",
        host,
        "--port",
        port,
    ],
    "WorkingDirectory": project_root,
    "EnvironmentVariables": {
        "OLLAMA_BASE_URL": ollama_base_url,
        "OLLAMA_MODEL": model,
        "DEFAULT_SOURCE_LANG": source_lang,
        "DEFAULT_TARGET_LANG": target_lang,
    },
    "RunAtLoad": True,
    "KeepAlive": True,
    "StandardOutPath": f"{log_dir}/stdout.log",
    "StandardErrorPath": f"{log_dir}/stderr.log",
}

with Path(plist_path).open("wb") as plist_file:
    plistlib.dump(plist, plist_file)
PY
  plutil -lint "$PLIST_PATH"
  launchctl bootout gui/$UID "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl bootstrap gui/$UID "$PLIST_PATH" || die "Failed to bootstrap LaunchAgent. Check $PLIST_PATH and logs in $LOG_DIR."
  launchctl kickstart -k gui/$UID/com.local.translate-service || die "Failed to start LaunchAgent. Run: launchctl print gui/$UID/$LABEL"
  launchctl print "gui/$UID/$LABEL" >/dev/null || die "Failed to verify LaunchAgent. Run: launchctl print gui/$UID/$LABEL and check logs in $LOG_DIR."
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
