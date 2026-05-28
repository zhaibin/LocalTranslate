# Project Handoff

Date: 2026-05-28

## Current State

The project is a local Ollama-backed translation service for `translategemma:latest`.
The current baseline on `main` provides five local entry points:

- HTTP API: `/translate`, `/languages`, `/health`
- Local Web UI: `/`
- Chrome extension: `chrome_extension/`
- CLI: `.venv/bin/translate`
- MCP stdio server: `python -m translate_service.mcp_server`

## Key Requirements Implemented

- TranslateGemma prompt format is implemented with exactly two blank lines before the text to translate.
- Default model is `translategemma:latest`.
- Supported languages are loaded from `translate_service/language_data.tsv`.
- The OpenAI-compatible entry point was intentionally removed from the design; MCP is the third integration entry point.
- GitHub, macOS, Linux, and Windows deployment scripts are implemented.
- Local Web UI is implemented without Node, npm, React, Vite, or any frontend build step.
- Chrome extension is implemented as a static Manifest V3 extension with no npm or build step.
- Chrome extension calls the local HTTP API from extension contexts; content scripts only render the page overlay.

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
- `chrome_extension/manifest.json`: Chrome Manifest V3 extension definition.
- `chrome_extension/background.js`: context menu, settings, local API calls, and fallback routing.
- `chrome_extension/content_script.js`: in-page translation overlay.
- `chrome_extension/popup.html`, `chrome_extension/popup.js`: manual extension popup translation.
- `chrome_extension/options.html`, `chrome_extension/options.js`: extension settings and service checks.
- `chrome_extension/result.html`, `chrome_extension/result.js`: fallback result page for restricted pages.
- `chrome_extension/styles.css`: shared extension page styling.
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

## Chrome Extension

The Chrome extension lives in `chrome_extension/` and is loaded manually as an
unpacked extension during local use.

Start the local service first:

```bash
.venv/bin/translate serve --host 127.0.0.1 --port 8000
```

In Chrome, open the extensions page, enable Developer mode, choose **Load
unpacked**, and select the `chrome_extension/` directory.

The extension currently includes:

- Right-click translation for selected webpage text.
- In-page overlay with loading, result, error, copy, and close states.
- Fallback `result.html` page when the content script cannot be injected.
- Popup manual translation flow.
- Options page for service URL and default source/target languages.

Defaults:

- Service URL: `http://127.0.0.1:8000`
- Source language: `en`
- Target language: `zh`

Extension storage behavior:

- `chrome.storage.local` stores only settings.
- `chrome.storage.session` stores only the latest fallback result for the current browser session.
- Translation history is not persisted.

Chrome manual verification was completed after loading the unpacked extension
from `chrome_extension/`.

## Verification Commands

Run full regression:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
node --check translate_service/web/static/app.js
node --check chrome_extension/background.js
node --check chrome_extension/content_script.js
node --check chrome_extension/popup.js
node --check chrome_extension/options.js
node --check chrome_extension/result.js
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
- Chrome extension loads as an unpacked extension from `chrome_extension/`.
- Chrome extension right-click translation and popup translation work against the local service.
- Real translation works when local Ollama is running and `translategemma:latest` is available.
- README documents CLI, HTTP, MCP, Web UI, Chrome extension, and cross-platform deployment.

## Recent Context

- `ad33eee merge: chrome extension local translation`
- `0cedbff test: scope chrome extension README assertions`
- `1968c42 docs: document chrome extension usage`
- `c7a68e4 fix: keep extension language selects valid`
- `8059192 fix: harden popup language and result handling`
- `999b9cb feat: add translation overlay and fallback result page`
- `d5dc087 fix: harden chrome extension background contract`
- `0c3a22d feat: add chrome extension manifest and background core`

## Known Notes For Next Session

- Use `.venv/bin/translate`, not bare `translate`, unless the environment has explicitly activated the virtualenv or installed the package into PATH.
- `.env` and `.env.backup.*` are intentionally gitignored because the installer writes local configuration.
- If a server is already running on port `8000`, stop it before starting another one or choose another port.
- Browser automation via Playwright may not be installed in the Node REPL environment; HTTP smoke tests are sufficient unless browser tooling is available.
- Chrome extension GUI verification is manual: load `chrome_extension/` as an unpacked extension, select text on a normal webpage, use the context menu, and test the popup/options pages.
- The Chrome extension uses a 25-second request timeout in the background service worker to avoid Chrome Manifest V3 service worker long-fetch termination.
- Chrome manifest icons are PNG files. Do not switch the manifest back to SVG icons.
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
