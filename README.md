# Local Ollama Translation Service

Local translation service for Ollama and `translategemma:latest`.

The project provides four local entry points:

- Web UI: `http://127.0.0.1:8000/`
- HTTP API: `/translate`, `/languages`, `/health`
- CLI: `.venv/bin/translate`
- MCP stdio server: `python -m translate_service.mcp_server`

## GitHub One-Line Install

Use this path for a fresh install from GitHub:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)"
```

The bootstrap script detects the operating system, deploys the code to
`~/.local/share/local-translate`, installs or prepares Ollama, pulls
`translategemma:latest`, and installs the local HTTP service.

Prerequisites for the bootstrap command:

- macOS or Linux: `bash`, `curl`, `git`, Python 3.11+
- macOS Ollama auto-install: Homebrew
- Linux Ollama auto-install: official Ollama install script
- Windows: Git Bash plus Windows PowerShell or PowerShell 7+, Python 3.11+, and
  `winget` when using Ollama auto-install

Common options:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)" -- --install-dir "$HOME/apps/local-translate"
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)" -- --no-install-service
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)" -- --no-install-ollama --no-pull-model
```

Environment overrides are also supported:

```bash
LOCALTRANSLATE_INSTALL_DIR="$HOME/apps/local-translate" \
LOCALTRANSLATE_REF=main \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)"
```

After service install, check:

```bash
curl http://127.0.0.1:8000/health
```

## Requirements

Manual or checkout-based installs need:

- Python 3.11+
- A running Ollama server
- The `translategemma:latest` model installed locally

```bash
ollama pull translategemma:latest
```

## macOS One-Command Install

Prerequisites:

- macOS
- Python 3.11+
- Ollama

If Ollama is not installed, the installer can prepare it with `--install-ollama`.
That option requires Homebrew; it does not install Homebrew for you.

Default CLI install from the project checkout:

```bash
scripts/install_macos.sh
```

Install and prepare Ollama plus the default model:

```bash
scripts/install_macos.sh --install-ollama
```

Install the HTTP API as a per-user LaunchAgent service:

```bash
scripts/install_macos.sh --install-service
```

Prepare Ollama/model and install the user service in one command:

```bash
scripts/install_macos.sh --install-ollama --install-service
```

Manage the service with:

```bash
launchctl print gui/$UID/com.local.translate-service
launchctl kickstart -k gui/$UID/com.local.translate-service
```

Service logs are written to:

```text
~/Library/Logs/translate-service/stdout.log
~/Library/Logs/translate-service/stderr.log
~/Library/Logs/translate-service/ollama.log
```

Uninstall the user service with:

```bash
scripts/uninstall_macos.sh
```

To also remove the project virtual environment:

```bash
scripts/uninstall_macos.sh --remove-venv
```

The uninstaller keeps Ollama and downloaded models by default.

## Linux One-Command Install

Prerequisites:

- Linux with `bash`
- Python 3.11+
- Ollama

If Ollama is not installed, the installer can prepare it with `--install-ollama`.
That option uses Ollama's official Linux installer.

Default CLI install from the project checkout:

```bash
scripts/install_linux.sh
```

Install and prepare Ollama plus the default model:

```bash
scripts/install_linux.sh --install-ollama
```

Install the HTTP API as a per-user systemd service:

```bash
scripts/install_linux.sh --install-service
```

Prepare Ollama/model and install the user service in one command:

```bash
scripts/install_linux.sh --install-ollama --install-service
```

Manage the service with:

```bash
systemctl --user status translate-service.service
systemctl --user restart translate-service.service
journalctl --user -u translate-service.service
```

Uninstall the user service with:

```bash
scripts/uninstall_linux.sh
```

To also remove the project virtual environment:

```bash
scripts/uninstall_linux.sh --remove-venv
```

The uninstaller keeps Ollama and downloaded models by default.

## Windows PowerShell Install

Prerequisites:

- Windows PowerShell or PowerShell 7+
- Python 3.11+
- Ollama

If Ollama is not installed, the installer can prepare it with `-InstallOllama`.
That option requires `winget`; it does not install `winget` for you.

Default CLI install from the project checkout:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
```

Install and prepare Ollama plus the default model:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -InstallOllama
```

Install the HTTP API as a per-user scheduled task:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -InstallService
```

Prepare Ollama/model and install the user scheduled task in one command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -InstallOllama -InstallService
```

If scheduled task registration returns `Access is denied`, rerun the command
from an interactive PowerShell session, using Run as Administrator if your
Windows policy requires it.

Manage the scheduled task with:

```powershell
Get-ScheduledTask -TaskName TranslateService
Start-ScheduledTask -TaskName TranslateService
Stop-ScheduledTask -TaskName TranslateService
```

Uninstall the scheduled task with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_windows.ps1
```

To also remove the project virtual environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_windows.ps1 -RemoveVenv
```

The uninstaller keeps Ollama and downloaded models by default.

## Configuration

The installers write `.env` in the project directory. For manual setup, copy the
example file and adjust values if your Ollama host, model, or default languages
differ.

```bash
cp .env.example .env
```

Defaults use English (`en`) as the source language and Chinese (`zh`) as the
target language. Pass explicit language codes per request to override them.

## CLI

```bash
.venv/bin/translate text --from en --to zh "Hello"
.venv/bin/translate languages
.venv/bin/translate serve --host 127.0.0.1 --port 8000
```

## Local Web UI

Start the local HTTP server:

```bash
.venv/bin/translate serve --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/
```

The page uses the same local API endpoints as other clients: `/translate` for
translation, `/languages` for supported language choices, and `/health` for
service status.

## HTTP

Start the API server:

```bash
.venv/bin/translate serve --host 127.0.0.1 --port 8000
```

Translate text:

```bash
curl -X POST http://127.0.0.1:8000/translate \
  -H 'content-type: application/json' \
  -d '{"text":"Hello","source_lang":"en","target_lang":"zh"}'
```

List languages and check service health:

```bash
curl http://127.0.0.1:8000/languages
curl http://127.0.0.1:8000/health
```

Expected healthy response when Ollama and the model are available:

```json
{
  "status": "ok",
  "model": "translategemma:latest",
  "ollama": {
    "ok": true,
    "model_available": true
  }
}
```

## MCP

Run the MCP stdio server with:

```bash
python -m translate_service.mcp_server
```

Available MCP tools:

- `translate_text`: translate text with optional source and target language codes.
- `list_languages`: return supported language codes.
- `health`: check the configured Ollama model status.

## Maintenance

Project handoff and current implementation notes live in
`docs/handoff.md`.

Run local checks before publishing changes:

```bash
pytest -q
ruff check .
node --check translate_service/web/static/app.js
bash -n scripts/install.sh
bash -n scripts/install_macos.sh
bash -n scripts/uninstall_macos.sh
bash -n scripts/install_linux.sh
bash -n scripts/uninstall_linux.sh
python -c 'from translate_service.prompt import build_prompt; p=build_prompt(source_name="English",source_code="en",target_name="Chinese",target_code="zh",text="Hello"); print(repr(p[-12:]))'
```

Run Windows installer checks inside a Windows environment. Use a VM-internal
checkout or copy for install tests so Windows `.venv` files do not overwrite
the macOS project virtual environment through a shared folder.
