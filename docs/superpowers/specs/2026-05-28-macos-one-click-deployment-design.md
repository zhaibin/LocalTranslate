# macOS One-Click Deployment Design

Date: 2026-05-28

## Goal

Add a one-command macOS deployment path for the local Ollama translation service. A user should be able to clone or copy the project to another Mac, run one install script, and get the CLI plus an optional user-level HTTP background service.

The first version targets transparent local installation from the project directory. It does not build a signed app, installer package, Homebrew formula, or fully offline bundle.

## User Experience

Primary command:

```bash
./scripts/install_macos.sh --install-service --install-ollama
```

Common variants:

```bash
./scripts/install_macos.sh
./scripts/install_macos.sh --install-service
./scripts/install_macos.sh --install-service --no-pull-model
```

Uninstall:

```bash
./scripts/uninstall_macos.sh
./scripts/uninstall_macos.sh --remove-venv
```

## Install Script

Create `scripts/install_macos.sh`.

Supported options:

```text
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
--help                  Print usage.
```

Install steps:

1. Check the host is macOS.
2. Check the script is running from a valid project checkout.
3. Find Python 3.11+.
4. Check Ollama.
5. If Ollama is missing and `--install-ollama` is set, install Ollama with Homebrew.
6. Create `.venv` in the project directory.
7. Install the project into `.venv` with `python -m pip install -e .`.
8. Write `.env` with configured Ollama/model/default language values.
9. Pull the configured model unless `--no-pull-model` is set.
10. If `--install-service` is set, write and start the LaunchAgent.
11. Run final health checks and print next commands.

The script should print clear stage messages such as:

```text
[1/7] Checking macOS and Python
[2/7] Checking Ollama
```

## Ollama Handling

Default behavior is conservative: the installer checks for Ollama and stops if it is missing.

If the user passes `--install-ollama`, the script may run:

```bash
brew install ollama
```

If Homebrew is missing, the script stops and tells the user to install Homebrew or install Ollama manually. The script should not install Homebrew.

The installer should pull the model by default:

```bash
ollama pull translategemma:latest
```

`--no-pull-model` skips this step.

## Configuration

The installer writes `.env` in the project directory:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=translategemma:latest
DEFAULT_SOURCE_LANG=en
DEFAULT_TARGET_LANG=zh
REQUEST_TIMEOUT_SECONDS=120
```

Values are driven by installer flags.

## LaunchAgent Service

When `--install-service` is set, create:

```text
~/Library/LaunchAgents/com.local.translate-service.plist
```

The service command should use absolute paths:

```bash
/absolute/path/to/project/.venv/bin/translate serve --host 127.0.0.1 --port 8000
```

Logs:

```text
~/Library/Logs/translate-service/stdout.log
~/Library/Logs/translate-service/stderr.log
```

The installer should create the log directory and then run:

```bash
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.local.translate-service.plist
launchctl kickstart -k gui/$UID/com.local.translate-service
```

If a service with the same label is already loaded, the installer should boot it out before bootstrapping the updated plist.

## Uninstall Script

Create `scripts/uninstall_macos.sh`.

Supported options:

```text
--remove-venv           Remove the project .venv after unloading the service.
--help                  Print usage.
```

Uninstall steps:

1. Try to unload `com.local.translate-service` from `gui/$UID`.
2. Remove `~/Library/LaunchAgents/com.local.translate-service.plist`.
3. If `--remove-venv` is set, remove the project `.venv`.
4. Do not remove project source, Ollama, Ollama models, or user logs by default.

## Verification

Installer verification:

- Confirm `.venv/bin/translate --help` works.
- If service is installed, confirm `launchctl print gui/$UID/com.local.translate-service` succeeds.
- Check `http://HOST:PORT/health` when the service is installed.

Manual verification commands:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/translate \
  -H 'content-type: application/json' \
  -d '{"text":"Hello","source_lang":"en","target_lang":"zh"}'
```

Development verification:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
```

If `shellcheck` is available, run it on both scripts.

## Failure Handling

- Unsupported OS: stop with a macOS-only message.
- Python below 3.11: stop and tell the user to install Python 3.11+.
- Ollama missing without `--install-ollama`: stop and suggest `--install-ollama` or manual installation.
- Homebrew missing with `--install-ollama`: stop and tell the user to install Homebrew or Ollama manually.
- Model pull failure: stop with the model name and Ollama troubleshooting hint.
- LaunchAgent failure: print the plist path, log paths, and `launchctl print` command.
- `/health` degraded: do not hide the result; print the response so the user can see whether Ollama or the model is the problem.

## Documentation

Update `README.md` with:

- macOS one-command install.
- service install and uninstall commands.
- CLI-only install.
- how to check logs.
- how to verify HTTP translation.

## Non-Goals

The first version will not include:

- A signed `.pkg` installer.
- A `.app` bundle.
- A Homebrew formula.
- Fully offline dependency or model packaging.
- System-level LaunchDaemon installation.
- Automatic Homebrew installation.
