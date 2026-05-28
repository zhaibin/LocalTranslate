#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_URL="https://github.com/zhaibin/LocalTranslate.git"
DEFAULT_REF="main"
DEFAULT_INSTALL_DIR="${LOCALTRANSLATE_INSTALL_DIR:-$HOME/.local/share/local-translate}"

REPO_URL="${LOCALTRANSLATE_REPO_URL:-$DEFAULT_REPO_URL}"
REF="${LOCALTRANSLATE_REF:-$DEFAULT_REF}"
INSTALL_DIR="$DEFAULT_INSTALL_DIR"
INSTALL_OLLAMA=1
INSTALL_SERVICE=1
PULL_MODEL=1
INSTALL_ARGS=()

usage() {
  cat <<'EOF'
Usage: bash scripts/install.sh [options]

Bootstrap LocalTranslate from GitHub, detect the operating system, then run the
platform installer.

Defaults install/prepare Ollama, pull the default model, and install the local
HTTP service.

Bootstrap options:
  --install-dir DIR       Local checkout/deployment directory.
                          Default: ~/.local/share/local-translate
  --repo-url URL          Git repository URL.
                          Default: https://github.com/zhaibin/LocalTranslate.git
  --ref REF               Git branch, tag, or commit to install. Default: main.
  --install-ollama        Install Ollama if missing. Default.
  --no-install-ollama     Do not install Ollama.
  --install-service       Install and start the local HTTP service. Default.
  --no-install-service    Install CLI/config only; do not install the service.
  --pull-model            Pull/update the configured Ollama model. Default.
  --no-pull-model         Skip model pull.

Forwarded installer options:
  --host HOST
  --port PORT
  --model MODEL
  --source-lang CODE
  --target-lang CODE
  --ollama-base-url URL
  --help
EOF
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_value() {
  option="$1"
  value="${2:-}"
  [ -n "$value" ] || die "$option requires a value"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install-dir)
      require_value "$1" "${2:-}"
      INSTALL_DIR="$2"
      shift 2
      ;;
    --repo-url)
      require_value "$1" "${2:-}"
      REPO_URL="$2"
      shift 2
      ;;
    --ref)
      require_value "$1" "${2:-}"
      REF="$2"
      shift 2
      ;;
    --install-ollama)
      INSTALL_OLLAMA=1
      shift
      ;;
    --no-install-ollama)
      INSTALL_OLLAMA=0
      shift
      ;;
    --install-service)
      INSTALL_SERVICE=1
      shift
      ;;
    --no-install-service)
      INSTALL_SERVICE=0
      shift
      ;;
    --pull-model)
      PULL_MODEL=1
      shift
      ;;
    --no-pull-model)
      PULL_MODEL=0
      shift
      ;;
    --host|--port|--model|--source-lang|--target-lang|--ollama-base-url)
      require_value "$1" "${2:-}"
      INSTALL_ARGS+=("$1" "$2")
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

case "$INSTALL_DIR" in
  ""|*[[:space:]]*)
    die "--install-dir must not be empty or contain whitespace."
    ;;
esac

command -v git >/dev/null 2>&1 || die "git is required to deploy code from GitHub."

UNAME="$(uname -s)"
case "$UNAME" in
  Darwin)
    PLATFORM="macos"
    PLATFORM_SCRIPT="scripts/install_macos.sh"
    ;;
  Linux)
    PLATFORM="linux"
    PLATFORM_SCRIPT="scripts/install_linux.sh"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    PLATFORM="windows"
    PLATFORM_SCRIPT="scripts/install_windows.ps1"
    ;;
  *)
    die "Unsupported operating system: $UNAME"
    ;;
esac

log "[1/3] Deploying LocalTranslate code"
if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" fetch --tags origin "$REF"
else
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone "$REPO_URL" "$INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch --tags origin "$REF"
fi
git -C "$INSTALL_DIR" checkout --detach FETCH_HEAD

log "[2/3] Preparing $PLATFORM installer"
if [ "$INSTALL_OLLAMA" -eq 1 ]; then
  INSTALL_ARGS+=("--install-ollama")
fi
if [ "$INSTALL_SERVICE" -eq 1 ]; then
  INSTALL_ARGS+=("--install-service")
fi
if [ "$PULL_MODEL" -eq 1 ]; then
  INSTALL_ARGS+=("--pull-model")
else
  INSTALL_ARGS+=("--no-pull-model")
fi

log "[3/3] Running $PLATFORM installer"
case "$PLATFORM" in
  macos|linux)
    bash "$INSTALL_DIR/$PLATFORM_SCRIPT" "${INSTALL_ARGS[@]}"
    ;;
  windows)
    PS_ARGS=()
    index=0
    while [ "$index" -lt "${#INSTALL_ARGS[@]}" ]; do
      case "${INSTALL_ARGS[$index]}" in
        --install-ollama)
          PS_ARGS+=("-InstallOllama")
          index=$((index + 1))
          ;;
        --install-service)
          PS_ARGS+=("-InstallService")
          index=$((index + 1))
          ;;
        --no-pull-model)
          PS_ARGS+=("-NoPullModel")
          index=$((index + 1))
          ;;
        --pull-model)
          index=$((index + 1))
          ;;
        --host)
          PS_ARGS+=("-HostName" "${INSTALL_ARGS[$((index + 1))]}")
          index=$((index + 2))
          ;;
        --port)
          PS_ARGS+=("-Port" "${INSTALL_ARGS[$((index + 1))]}")
          index=$((index + 2))
          ;;
        --model)
          PS_ARGS+=("-Model" "${INSTALL_ARGS[$((index + 1))]}")
          index=$((index + 2))
          ;;
        --source-lang)
          PS_ARGS+=("-SourceLang" "${INSTALL_ARGS[$((index + 1))]}")
          index=$((index + 2))
          ;;
        --target-lang)
          PS_ARGS+=("-TargetLang" "${INSTALL_ARGS[$((index + 1))]}")
          index=$((index + 2))
          ;;
        --ollama-base-url)
          PS_ARGS+=("-OllamaBaseUrl" "${INSTALL_ARGS[$((index + 1))]}")
          index=$((index + 2))
          ;;
        *)
          die "Internal error: unsupported Windows installer option ${INSTALL_ARGS[$index]}"
          ;;
      esac
    done
    powershell.exe -ExecutionPolicy Bypass -File "$INSTALL_DIR/$PLATFORM_SCRIPT" "${PS_ARGS[@]}"
    ;;
esac

log "Bootstrap install complete."
