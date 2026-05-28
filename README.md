# Local Ollama Translation Service

Local translation service for Ollama and `translategemma:latest`.

## Requirements

- Python 3.11+
- A running Ollama server
- The `translategemma:latest` model installed locally:

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

After installing the service, check health at:

```bash
curl http://127.0.0.1:8000/health
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

## Configuration

Copy `.env.example` to `.env` and adjust values if your Ollama host, model, or default
languages differ.

```bash
cp .env.example .env
```

Defaults use English (`en`) as the source language and Chinese (`zh`) as the target
language. Pass explicit language codes per request to override them.

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

Then open the browser workbench at:

```text
http://127.0.0.1:8000/
```

The page uses the same local API endpoints as other clients: `/translate` for
translation, `/languages` for supported language choices, and `/health` for
service status. If the macOS `--install-service` option is installed, the
LaunchAgent serves the same web UI at `http://127.0.0.1:8000/`.

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

## MCP

Run the MCP stdio server with:

```bash
python -m translate_service.mcp_server
```

Available MCP tools:

- `translate_text`: translate text with optional source and target language codes.
- `list_languages`: return supported language codes.
- `health`: check the configured Ollama model status.

## Development Checks

```bash
pytest -q
ruff check .
python -c 'from translate_service.prompt import build_prompt; p=build_prompt(source_name="English",source_code="en",target_name="Chinese",target_code="zh",text="Hello"); print(repr(p[-12:]))'
```
