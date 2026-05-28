# Phase 1 Handoff

Date: 2026-05-28

## Current State

Phase 1 is complete on `main`.

The project is a local Ollama-backed translation service for `translategemma:latest`.
It now provides four entry points:

- HTTP API: `/translate`, `/languages`, `/health`
- Local Web UI: `/`
- CLI: `.venv/bin/translate`
- MCP stdio server: `python -m translate_service.mcp_server`

The current working tree was clean when this handoff was written.

## Key Requirements Implemented

- TranslateGemma prompt format is implemented with exactly two blank lines before the text to translate.
- Default model is `translategemma:latest`.
- Supported languages are loaded from `translate_service/language_data.tsv`.
- The OpenAI-compatible entry point was intentionally removed from the design; MCP is the third integration entry point.
- macOS one-command deployment is implemented.
- Local Web UI is implemented without Node, npm, React, Vite, or any frontend build step.

## Important Files

- `translate_service/service.py`: translation orchestration.
- `translate_service/prompt.py`: TranslateGemma prompt builder.
- `translate_service/ollama_client.py`: Ollama HTTP client.
- `translate_service/api/app.py`: FastAPI app factory, Web UI static mount, exception handlers.
- `translate_service/api/routes_translate.py`: `/translate`.
- `translate_service/api/routes_system.py`: `/languages` and `/health`.
- `translate_service/web/static/index.html`: Web UI markup.
- `translate_service/web/static/styles.css`: Web UI styling.
- `translate_service/web/static/app.js`: Web UI browser logic.
- `translate_service/cli.py`: CLI commands.
- `translate_service/mcp_server.py`: MCP stdio tools.
- `scripts/install_macos.sh`: macOS installer.
- `scripts/uninstall_macos.sh`: macOS uninstaller.
- `README.md`: user-facing setup and usage docs.

## macOS Deployment

Install from the project checkout:

```bash
scripts/install_macos.sh
```

Install Ollama/model support when needed:

```bash
scripts/install_macos.sh --install-ollama
```

Install as a per-user LaunchAgent:

```bash
scripts/install_macos.sh --install-service
```

Uninstall the user service:

```bash
scripts/uninstall_macos.sh
```

Optionally remove the project virtual environment:

```bash
scripts/uninstall_macos.sh --remove-venv
```

The uninstaller intentionally keeps Ollama, downloaded models, project source, and logs by default.

## Local Web UI

Start the service:

```bash
.venv/bin/translate serve --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

The Web UI currently includes:

- Source text textarea.
- Source language selector.
- Target language selector.
- Swap language button.
- Translate button.
- Translation result textarea.
- Copy result button.
- Health/status display.
- Inline error/status messages.

The language search inputs were removed as unnecessary for Phase 1.

## Verification Commands

Run full regression:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
node --check translate_service/web/static/app.js
bash -n scripts/install_macos.sh
bash -n scripts/uninstall_macos.sh
```

Run local Web/API smoke:

```bash
.venv/bin/translate serve --host 127.0.0.1 --port 8000
curl -fsS http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/static/app.js
curl -fsS http://127.0.0.1:8000/health
```

Expected health result when Ollama and model are available:

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

## Phase 1 Acceptance Standard

Phase 1 is accepted when all of these are true:

- Full test suite passes.
- Ruff passes.
- macOS installer and uninstaller pass bash syntax checks.
- `node --check translate_service/web/static/app.js` passes.
- `GET /` serves the Web UI.
- `GET /static/app.js` serves browser logic.
- `GET /health` reports the configured model status.
- Real translation works when local Ollama is running and `translategemma:latest` is available.
- README documents CLI, HTTP, MCP, Web UI, and macOS deployment.

## Recent Important Commits

- `188b4dd fix: simplify language selectors`
- `cbc9900 docs: use local translate entrypoint`
- `4aa4180 docs: document local web UI`
- `cb8e5c2 fix: preserve filtered language selections`
- `30e8578 feat: add browser translation workbench`
- `f18003e feat: serve local web translation UI`
- `ee5a500 fix: keep macOS installer artifacts local`
- `9596752 feat: add macOS uninstaller script`

## Known Notes For Next Session

- Use `.venv/bin/translate`, not bare `translate`, unless the environment has explicitly activated the virtualenv or installed the package into PATH.
- `.env` and `.env.backup.*` are intentionally gitignored because the installer writes local configuration.
- If a server is already running on port `8000`, stop it before starting another one or choose another port.
- Browser automation via Playwright may not be installed in the Node REPL environment; HTTP smoke tests are sufficient unless browser tooling is available.
- Do not reintroduce an OpenAI-compatible endpoint unless the product direction changes.
