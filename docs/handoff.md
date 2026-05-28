# Project Handoff

Date: 2026-05-28

## Current State

The project is a local Ollama-backed translation service for `translategemma:latest`.
The current baseline on `main` provides four entry points:

- HTTP API: `/translate`, `/languages`, `/health`
- Local Web UI: `/`
- CLI: `.venv/bin/translate`
- MCP stdio server: `python -m translate_service.mcp_server`

## Key Requirements Implemented

- TranslateGemma prompt format is implemented with exactly two blank lines before the text to translate.
- Default model is `translategemma:latest`.
- Supported languages are loaded from `translate_service/language_data.tsv`.
- The OpenAI-compatible entry point was intentionally removed from the design; MCP is the third integration entry point.
- GitHub, macOS, Linux, and Windows deployment scripts are implemented.
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
- `scripts/install.sh`: GitHub bootstrap installer.
- `scripts/install_macos.sh`: macOS installer.
- `scripts/uninstall_macos.sh`: macOS uninstaller.
- `scripts/install_linux.sh`: Linux installer.
- `scripts/uninstall_linux.sh`: Linux uninstaller.
- `scripts/install_windows.ps1`: Windows installer.
- `scripts/uninstall_windows.ps1`: Windows uninstaller.
- `README.md`: user-facing setup and usage docs.

## GitHub Bootstrap Install

Install from the GitHub-hosted bootstrap script:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)"
```

By default it deploys the code to `~/.local/share/local-translate`, installs or
prepares Ollama, pulls the default model, and installs the local HTTP service.

Useful options:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)" -- --install-dir "$HOME/apps/local-translate"
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)" -- --no-install-service
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh)" -- --no-install-ollama --no-pull-model
```

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

The language search inputs were removed to keep the browser UI focused and simple.

## Verification Commands

Run full regression:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
node --check translate_service/web/static/app.js
bash -n scripts/install.sh
bash -n scripts/install_macos.sh
bash -n scripts/uninstall_macos.sh
bash -n scripts/install_linux.sh
bash -n scripts/uninstall_linux.sh
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

## Current Baseline Standard

The project baseline is healthy when all of these are true:

- Full test suite passes.
- Ruff passes.
- GitHub bootstrap, macOS, and Linux installer/uninstaller scripts pass bash syntax checks.
- `node --check translate_service/web/static/app.js` passes.
- `GET /` serves the Web UI.
- `GET /static/app.js` serves browser logic.
- `GET /health` reports the configured model status.
- Real translation works when local Ollama is running and `translategemma:latest` is available.
- README documents CLI, HTTP, MCP, Web UI, and cross-platform deployment.

## Recent Context

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

## Cross-Platform Deployment

Cross-platform deployment support includes:

- GitHub bootstrap installer: `scripts/install.sh`.
- macOS installer and uninstaller: `scripts/install_macos.sh`, `scripts/uninstall_macos.sh`.
- Linux installer and uninstaller: `scripts/install_linux.sh`, `scripts/uninstall_linux.sh`.
- Windows installer and uninstaller: `scripts/install_windows.ps1`, `scripts/uninstall_windows.ps1`.
- Cross-platform deployment tests: `tests/test_cross_platform_scripts.py`.

Linux service mode installs a per-user `systemd --user` service named
`translate-service.service`.

Windows service mode installs a per-user scheduled task named `TranslateService`.

The Linux and Windows uninstallers intentionally keep Ollama, downloaded models,
project source, and logs by default, matching the conservative macOS uninstaller.

Windows installer/runtime verification should be performed in the local
Parallels Desktop Windows VM.

Windows test notes from 2026-05-28:

- Use a VM-internal checkout or copy for installer tests. Running the installer
  directly from a Parallels shared folder can overwrite the macOS `.venv`
  metadata with Windows paths.
- Windows 11 ARM64 with Python 3.12 installs successfully when
  `cryptography==46.0.3` is pinned; newer `cryptography` releases selected by
  pip did not have a compatible wheel and attempted a failing OpenSSL source
  build.
- CLI `languages` output and the local HTTP `/health` smoke path were verified
  in the VM.
- `-InstallService` currently fails under `prlctl exec --current-user` because
  Windows denies scheduled task creation in that execution context. The script
  now fails fast instead of reporting success. Verify scheduled task creation
  from an interactive Windows PowerShell session, using Run as Administrator if
  Windows policy requires it.
