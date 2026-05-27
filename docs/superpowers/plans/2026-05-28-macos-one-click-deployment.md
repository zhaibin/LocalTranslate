# macOS One-Click Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one-command macOS installation, service setup, and uninstall scripts for the local Ollama translation service.

**Architecture:** Keep deployment concerns in `scripts/` and documentation, leaving translation service code unchanged. Shell scripts install the Python package into a project-local `.venv`, optionally manage Ollama/model setup, and optionally install a user LaunchAgent that runs the existing `translate serve` CLI.

**Tech Stack:** POSIX shell with macOS utilities (`launchctl`, `plutil`, `curl`), Python venv/pip, existing Python test suite, optional ShellCheck.

---

## File Structure

Create:

- `scripts/install_macos.sh`: one-command installer and optional LaunchAgent setup.
- `scripts/uninstall_macos.sh`: user LaunchAgent uninstaller and optional `.venv` remover.
- `tests/test_macos_scripts.py`: static and behavioral tests for script content, options, plist generation helpers, and safety expectations.

Modify:

- `README.md`: add macOS deployment instructions.

No translation service Python modules should change unless a test reveals a true integration bug.

---

### Task 1: macOS Installer Script

**Files:**
- Create: `scripts/install_macos.sh`
- Test: `tests/test_macos_scripts.py`

- [ ] **Step 1: Write failing installer tests**

Create `tests/test_macos_scripts.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "scripts" / "install_macos.sh"
UNINSTALL_SCRIPT = ROOT / "scripts" / "uninstall_macos.sh"


def read_script(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_install_script_exists_and_is_executable():
    assert INSTALL_SCRIPT.exists()
    assert INSTALL_SCRIPT.stat().st_mode & 0o111


def test_install_script_exposes_expected_options():
    script = read_script(INSTALL_SCRIPT)

    for option in [
        "--install-service",
        "--install-ollama",
        "--pull-model",
        "--no-pull-model",
        "--host",
        "--port",
        "--model",
        "--source-lang",
        "--target-lang",
        "--ollama-base-url",
        "--help",
    ]:
        assert option in script


def test_install_script_uses_project_local_virtualenv_and_editable_install():
    script = read_script(INSTALL_SCRIPT)

    assert 'VENV_DIR="$PROJECT_ROOT/.venv"' in script
    assert '"$PYTHON_BIN" -m venv "$VENV_DIR"' in script
    assert '"$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"' in script


def test_install_script_writes_env_and_launchagent_paths():
    script = read_script(INSTALL_SCRIPT)

    assert "OLLAMA_MODEL=" in script
    assert "DEFAULT_SOURCE_LANG=" in script
    assert "DEFAULT_TARGET_LANG=" in script
    assert "com.local.translate-service.plist" in script
    assert "Library/LaunchAgents" in script
    assert "Library/Logs/translate-service" in script


def test_install_script_uses_user_launchagent_not_system_daemon():
    script = read_script(INSTALL_SCRIPT)

    assert "launchctl bootstrap gui/$UID" in script
    assert "launchctl kickstart -k gui/$UID/com.local.translate-service" in script
    assert "/Library/LaunchDaemons" not in script
    assert "sudo " not in script
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py -q
```

Expected: FAIL because `scripts/install_macos.sh` does not exist.

- [ ] **Step 3: Implement installer script**

Create `scripts/install_macos.sh`:

```bash
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
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
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
  launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$UID" "$PLIST_PATH" || die "Failed to bootstrap LaunchAgent. Check $PLIST_PATH and logs in $LOG_DIR."
  launchctl kickstart -k "gui/$UID/$LABEL" || die "Failed to start LaunchAgent. Run: launchctl print gui/$UID/$LABEL"
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
```

- [ ] **Step 4: Make script executable**

Run:

```bash
chmod +x scripts/install_macos.sh
```

Expected: command exits 0.

- [ ] **Step 5: Run installer tests**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py -q
```

Expected: PASS for installer tests.

- [ ] **Step 6: Commit installer**

```bash
git add scripts/install_macos.sh tests/test_macos_scripts.py
git commit -m "feat: add macOS installer script"
```

---

### Task 2: macOS Uninstall Script

**Files:**
- Create: `scripts/uninstall_macos.sh`
- Modify: `tests/test_macos_scripts.py`

- [ ] **Step 1: Add failing uninstall tests**

Append to `tests/test_macos_scripts.py`:

```python
def test_uninstall_script_exists_and_is_executable():
    assert UNINSTALL_SCRIPT.exists()
    assert UNINSTALL_SCRIPT.stat().st_mode & 0o111


def test_uninstall_script_unloads_user_launchagent_and_preserves_user_assets():
    script = read_script(UNINSTALL_SCRIPT)

    assert "--remove-venv" in script
    assert "launchctl bootout gui/$UID" in script
    assert "com.local.translate-service.plist" in script
    assert "Library/LaunchAgents" in script
    assert "rm -rf \"$PROJECT_ROOT/.venv\"" in script
    assert "ollama rm" not in script
    assert "sudo " not in script
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py::test_uninstall_script_exists_and_is_executable -q
```

Expected: FAIL because `scripts/uninstall_macos.sh` does not exist.

- [ ] **Step 3: Implement uninstall script**

Create `scripts/uninstall_macos.sh`:

```bash
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$(uname -s)" != "Darwin" ]; then
  die "This uninstaller only supports macOS."
fi

log "Unloading LaunchAgent if it is loaded"
launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true

if [ -f "$PLIST_PATH" ]; then
  log "Removing $PLIST_PATH"
  rm -f "$PLIST_PATH"
else
  log "No LaunchAgent plist found at $PLIST_PATH"
fi

if [ "$REMOVE_VENV" -eq 1 ]; then
  log "Removing project virtual environment"
  rm -rf "$PROJECT_ROOT/.venv"
else
  log "Keeping project virtual environment. Pass --remove-venv to remove it."
fi

log "Uninstall complete. Project source, Ollama, models, and logs were not removed."
```

- [ ] **Step 4: Make script executable**

Run:

```bash
chmod +x scripts/uninstall_macos.sh
```

Expected: command exits 0.

- [ ] **Step 5: Run script tests**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit uninstaller**

```bash
git add scripts/uninstall_macos.sh tests/test_macos_scripts.py
git commit -m "feat: add macOS uninstaller script"
```

---

### Task 3: README Deployment Documentation

**Files:**
- Modify: `README.md`
- Test: `tests/test_macos_scripts.py`

- [ ] **Step 1: Add failing README tests**

Append to `tests/test_macos_scripts.py`:

```python
def test_readme_documents_macos_deployment_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "macOS One-Command Install" in readme
    assert "./scripts/install_macos.sh --install-service --install-ollama" in readme
    assert "./scripts/install_macos.sh" in readme
    assert "./scripts/uninstall_macos.sh --remove-venv" in readme
    assert "~/Library/Logs/translate-service" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py::test_readme_documents_macos_deployment_commands -q
```

Expected: FAIL because README does not yet document one-command install.

- [ ] **Step 3: Update README**

Add this section after Requirements:

````markdown
## macOS One-Command Install

From the project directory on a target Mac, install the CLI and configure a user-level
HTTP service:

```bash
./scripts/install_macos.sh --install-service --install-ollama
```

If Ollama is already installed, omit `--install-ollama`:

```bash
./scripts/install_macos.sh --install-service
```

Install only the CLI and local virtual environment:

```bash
./scripts/install_macos.sh
```

Skip model pulling when the model is already present:

```bash
./scripts/install_macos.sh --install-service --no-pull-model
```

The service is installed as:

```text
~/Library/LaunchAgents/com.local.translate-service.plist
```

Service logs are written to:

```text
~/Library/Logs/translate-service/stdout.log
~/Library/Logs/translate-service/stderr.log
```

Uninstall the service:

```bash
./scripts/uninstall_macos.sh
./scripts/uninstall_macos.sh --remove-venv
```
````

- [ ] **Step 4: Run README tests**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit docs**

```bash
git add README.md tests/test_macos_scripts.py
git commit -m "docs: add macOS deployment instructions"
```

---

### Task 4: Verification and Polish

**Files:**
- Modify only if verification finds issues: `scripts/install_macos.sh`, `scripts/uninstall_macos.sh`, `tests/test_macos_scripts.py`, `README.md`

- [ ] **Step 1: Run full Python test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run linting**

Run:

```bash
.venv/bin/ruff check .
```

Expected: PASS.

- [ ] **Step 3: Run shell syntax checks**

Run:

```bash
bash -n scripts/install_macos.sh
bash -n scripts/uninstall_macos.sh
```

Expected: both commands exit 0.

- [ ] **Step 4: Run ShellCheck if available**

Run:

```bash
if command -v shellcheck >/dev/null 2>&1; then shellcheck scripts/install_macos.sh scripts/uninstall_macos.sh; else echo "shellcheck not installed; skipping"; fi
```

Expected: ShellCheck passes, or the command prints `shellcheck not installed; skipping`.

- [ ] **Step 5: Smoke-test help output**

Run:

```bash
scripts/install_macos.sh --help
scripts/uninstall_macos.sh --help
```

Expected: both commands print usage and exit 0.

- [ ] **Step 6: Smoke-test installer non-service path**

Run:

```bash
scripts/install_macos.sh --no-pull-model
```

Expected: exits 0 on a macOS machine with Ollama available. It should create/update `.venv`, install the package, write `.env`, skip model pull, skip LaunchAgent, and print `Install complete.`

- [ ] **Step 7: Commit verification fixes if any**

If any script or test fixes were needed:

```bash
git add scripts/install_macos.sh scripts/uninstall_macos.sh tests/test_macos_scripts.py README.md
git commit -m "fix: polish macOS deployment scripts"
```

If no files changed, skip this commit.

---

## Plan Self-Review

Spec coverage:

- One-command installer: Task 1.
- Conservative Ollama detection plus `--install-ollama`: Task 1.
- Project-local `.venv` install: Task 1.
- `.env` writing: Task 1.
- LaunchAgent service, logs, bootout/bootstrap/kickstart: Task 1.
- Uninstall and optional `.venv` removal: Task 2.
- README deployment docs: Task 3.
- Tests, lint, shell syntax, optional ShellCheck, and non-service installer smoke test: Task 4.

Placeholder scan:

- No placeholder phrases remain.
- Commands, files, option names, and expected outputs are concrete.

Type and name consistency:

- LaunchAgent label is consistently `com.local.translate-service`.
- Plist path is consistently `~/Library/LaunchAgents/com.local.translate-service.plist`.
- Log directory is consistently `~/Library/Logs/translate-service`.
- Default model remains `translategemma:latest`.
