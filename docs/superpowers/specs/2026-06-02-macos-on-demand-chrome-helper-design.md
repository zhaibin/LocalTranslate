# macOS On-Demand Chrome Helper Design

## Goal

Make the Chrome extension recover from `failed to fetch` by starting the local translation stack on demand, then stop the stack after an idle period so the service does not consume resources when unused.

The first version supports macOS only.

## User Experience

When the Chrome extension cannot reach the local translation service:

1. The extension asks a macOS Chrome Native Messaging helper to ensure the local service is ready.
2. The helper starts Ollama when needed.
3. The helper starts the local translation HTTP service when needed.
4. The helper waits for `/health` to become reachable.
5. The extension retries the original translation request automatically.

When the stack is unused:

1. The translation HTTP service tracks recent activity.
2. If idle timeout is enabled and no request arrives before the configured timeout, the service exits.
3. On exit, the service stops Ollama only when the configured policy allows it.

Default idle timeout is 15 minutes.

## Scope

In scope:

- macOS Chrome Native Messaging helper.
- Explicit installer flag to register the helper.
- Extension retry flow after network-level local service failures.
- On-demand HTTP service mode with configurable idle timeout.
- Configurable Ollama stop policy.
- Safe helper protocol with no arbitrary shell execution.
- Tests for helper framing/protocol, service idle configuration, installer manifest generation, and extension integration markers.

Out of scope for the first version:

- Linux Native Messaging helper.
- Windows Native Messaging helper.
- Chrome Web Store packaging.
- Automatic discovery of Chrome extension ID.
- Automatic model pulling from the helper.
- Using a long-lived Native Messaging port to keep the helper resident.

## Architecture

```text
Chrome extension
  background.js
    -> fetch local /translate
    -> network failure
    -> chrome.runtime.sendNativeMessage("com.local.translate.helper", ensure_ready)
    -> helper returns ready
    -> retry /translate

Native Messaging helper
  local-translate-chrome-helper
    -> translate_service.chrome_helper:main
    -> validate request
    -> ensure Ollama is reachable
    -> ensure translate HTTP service is reachable
    -> return one JSON response

On-demand translate service
  .venv/bin/translate serve --idle-timeout-seconds 900
    -> update last activity on requests
    -> stop after idle timeout
    -> optionally stop helper-started Ollama
```

The helper does not stay resident. Chrome `sendNativeMessage()` starts a native host process for one request/response exchange, so the idle shutdown responsibility belongs to the HTTP service process, not the helper process.

## New Files

```text
translate_service/chrome_helper.py
tests/test_chrome_helper.py
tests/test_service_lifecycle.py
```

`translate_service/chrome_helper.py` responsibilities:

- Read and write Native Messaging frames on stdin/stdout.
- Validate helper messages.
- Normalize and validate local service URLs.
- Check Ollama readiness.
- Start local Ollama when unreachable.
- Check translation service readiness.
- Start translation service in on-demand mode when unreachable.
- Poll `/health` until ready or timeout.
- Write helper state used by the on-demand service exit path.

## Modified Files

```text
pyproject.toml
translate_service/cli.py
translate_service/api/app.py
chrome_extension/manifest.json
chrome_extension/background.js
chrome_extension/options.html
chrome_extension/options.js
scripts/install_macos.sh
scripts/uninstall_macos.sh
README.md
docs/handoff.md
tests/test_chrome_extension.py
tests/test_macos_scripts.py
```

## Console Script

Add a console script:

```toml
[project.scripts]
translate = "translate_service.cli:app"
local-translate-chrome-helper = "translate_service.chrome_helper:main"
```

Chrome Native Messaging host manifests require `path` to be an absolute executable path on macOS. A console script gives the manifest a stable executable path such as:

```text
/Users/.../translate/.venv/bin/local-translate-chrome-helper
```

## Native Messaging Registration

Installer flag:

```bash
scripts/install_macos.sh --install-chrome-helper --chrome-extension-id EXTENSION_ID
```

The flag explicitly opts in to the local process-starting capability.

Host manifest path:

```text
~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.local.translate.helper.json
```

Manifest shape:

```json
{
  "name": "com.local.translate.helper",
  "description": "Local Translate on-demand service helper",
  "path": "/absolute/path/to/.venv/bin/local-translate-chrome-helper",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://EXTENSION_ID/"
  ]
}
```

`allowed_origins` must contain the concrete extension ID. The installer should reject missing or malformed extension IDs when `--install-chrome-helper` is used.

The uninstaller should remove this manifest when present. It should keep Ollama, downloaded models, project source, logs, and `.venv` unless `--remove-venv` is requested.

## Helper Protocol

Requests:

```json
{ "type": "ping" }
```

```json
{
  "type": "ensure_ready",
  "service_url": "http://127.0.0.1:8000"
}
```

Responses:

```json
{
  "ok": true,
  "type": "pong"
}
```

```json
{
  "ok": true,
  "type": "ready",
  "service_url": "http://127.0.0.1:8000",
  "ollama_started": true,
  "translate_started": true
}
```

```json
{
  "ok": false,
  "error": "Ollama did not become ready within 30 seconds."
}
```

Native Messaging framing:

- Read 4-byte little-endian unsigned message length.
- Read exactly that many bytes.
- Parse UTF-8 JSON.
- Write one 4-byte little-endian unsigned length plus UTF-8 JSON response.
- Reject oversized messages. A 64 KiB maximum is sufficient for this helper.

## URL Validation

The helper accepts only:

- `http://127.0.0.1:<port>`
- `http://localhost:<port>`

It rejects:

- Non-HTTP schemes.
- Non-local hostnames.
- URLs with usernames/passwords.
- Paths other than `/` when used as the base service URL.
- Invalid or missing ports after normalization.

Default service URL:

```text
http://127.0.0.1:8000
```

## Process Lifecycle

### Ollama

The helper checks:

```text
GET http://127.0.0.1:11434/api/tags
```

If unreachable and the configured Ollama base URL is the default local URL, the helper starts:

```bash
ollama serve
```

The helper should prefer a conservative local start:

- If `ollama` is not on PATH, return an error.
- Start with `subprocess.Popen`.
- Redirect stdout/stderr to the existing log directory:
  `~/Library/Logs/translate-service/ollama.log`
- Record whether the helper started Ollama.

The helper should not install Ollama or pull models. Installation and model setup remain installer responsibilities.

### Translation Service

If `/health` is unreachable, the helper starts:

```bash
.venv/bin/translate serve \
  --host 127.0.0.1 \
  --port 8000 \
  --idle-timeout-seconds 900 \
  --stop-ollama-policy if-started-by-helper
```

Host and port are derived from the validated `service_url`.

The service process logs to:

```text
~/Library/Logs/translate-service/stdout.log
~/Library/Logs/translate-service/stderr.log
```

The helper records helper state:

```text
~/Library/Application Support/LocalTranslate/helper-state.json
```

State shape:

```json
{
  "translate_pid": 12345,
  "ollama_pid": 23456,
  "ollama_started_by_helper": true,
  "service_url": "http://127.0.0.1:8000",
  "started_at": "2026-06-02T12:00:00Z"
}
```

`ollama_pid` may be absent when Ollama was already running or when the helper
cannot confidently associate a process with its own start attempt. The default
stop policy must treat missing `ollama_pid` as "leave Ollama running."

## On-Demand Service Idle Shutdown

The CLI gains options:

```bash
.venv/bin/translate serve \
  --host 127.0.0.1 \
  --port 8000 \
  --idle-timeout-seconds 900 \
  --stop-ollama-policy if-started-by-helper
```

`--idle-timeout-seconds`:

- `0` disables idle shutdown.
- Default remains `0` for ordinary manual/server usage.
- Helper-started service uses `900` by default.

`--stop-ollama-policy`:

- `never`
- `if-started-by-helper` default for helper-started service
- `always`

The FastAPI app should update activity on:

- `/`
- `/static/...`
- `/health`
- `/languages`
- `/translate`

Implementation options:

- Add middleware that updates `app.state.last_activity_at` for every request.
- Add an async background task during app startup when idle timeout is enabled.
- When idle timeout expires, set `server.should_exit = True` through a uvicorn server wrapper instead of relying on abrupt process termination.

The current `uvicorn.run(create_app(), ...)` helper may need to change to explicit `uvicorn.Server` construction so the idle monitor can trigger graceful shutdown.

## Stopping Ollama

On service shutdown:

- `never`: do not stop Ollama.
- `if-started-by-helper`: stop Ollama only when helper state says `ollama_started_by_helper` is true and the PID still matches a running Ollama process.
- `always`: stop local Ollama even if not helper-started.

The first implementation should avoid broad `pkill ollama` by default. Prefer stopping the recorded PID when available. If recorded PID is unavailable, `if-started-by-helper` should leave Ollama running and log the reason.

## Chrome Extension Changes

Manifest:

```json
"permissions": [
  "contextMenus",
  "storage",
  "activeTab",
  "scripting",
  "nativeMessaging"
]
```

Background flow:

1. Call local API as today.
2. On network-level fetch failure, attempt `ensure_ready`.
3. If helper returns ready, retry the original request once.
4. If retry fails, show the retry failure.
5. If helper is unavailable, show a clear message:
   `Local service is not running and the Chrome helper is not installed.`

Do not call helper for backend application errors such as:

- Empty text.
- Unsupported language.
- Ollama model error returned by the service.
- Timeout returned by the service.

Call helper only for local service reachability failures.

Options page additions:

- Helper status row.
- `Test helper` button using `{ "type": "ping" }`.
- Idle timeout setting in minutes, default `15`.
- Ollama stop policy select with:
  - `never`
  - `if-started-by-helper`
  - `always`

For the first version, idle timeout and stop policy can be stored in extension settings and sent with `ensure_ready`. The helper should validate them and pass them to `translate serve`.

## Security Boundaries

- Helper accepts only `ping` and `ensure_ready`.
- Helper validates all message fields.
- Helper never executes arbitrary commands from Chrome.
- Helper only starts known executables:
  - `ollama serve`
  - the installed `translate` console script
- Helper only accepts localhost service URLs.
- Native Messaging host manifest restricts `allowed_origins` to one extension ID.
- Installer requires explicit `--install-chrome-helper`.
- Helper logs should not include source text or translated text.

## Error Handling

Extension user-facing errors:

- Helper missing: explain that the Chrome helper is not installed.
- Helper cannot start Ollama: explain that Ollama is missing or failed to start.
- Helper cannot start service: explain that the local translation service failed to start.
- Health timeout: show how long it waited.
- Retry failure after helper ready: show the retry error.

Helper errors should include enough diagnostics for startup problems but no translation content.

## Testing

Unit tests:

- Native Messaging frame decode/encode.
- Reject invalid JSON.
- Reject oversized messages.
- Reject unsupported message types.
- Validate local service URLs.
- Reject remote/non-HTTP URLs.
- `ping` returns `pong`.
- `ensure_ready` starts Ollama only when unreachable.
- `ensure_ready` starts translate service only when `/health` is unreachable.
- Helper writes state file when it starts processes.

Service lifecycle tests:

- CLI defaults keep idle shutdown disabled.
- CLI accepts `--idle-timeout-seconds`.
- CLI validates `--stop-ollama-policy`.
- Activity middleware updates timestamp on API and static requests.
- Idle monitor requests graceful shutdown after timeout.
- Ollama stop policy `never` does not stop Ollama.
- Ollama stop policy `if-started-by-helper` uses helper state.

Installer tests:

- `--install-chrome-helper` requires `--chrome-extension-id`.
- Invalid extension IDs are rejected.
- Native Messaging manifest path is correct.
- Native Messaging manifest `path` is absolute and points to the console script.
- Uninstaller removes the Native Messaging manifest.

Extension static tests:

- Manifest contains `nativeMessaging`.
- Background contains `sendNativeMessage`.
- Background retries local requests after helper readiness.
- Options page includes helper status, idle timeout, and Ollama stop policy controls.

Verification commands:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
node --check chrome_extension/background.js
node --check chrome_extension/options.js
```

Manual macOS verification:

1. Load the Chrome extension unpacked.
2. Copy the extension ID.
3. Run:
   ```bash
   scripts/install_macos.sh --install-chrome-helper --chrome-extension-id EXTENSION_ID
   ```
4. Stop the local translate service if running.
5. Stop Ollama if testing full cold start.
6. Select text in Chrome and translate.
7. Confirm the extension starts the service and retries automatically.
8. Wait for the configured idle timeout.
9. Confirm the translate service exits.
10. Confirm Ollama stop behavior matches the selected policy.

## Acceptance Criteria

- With helper installed, the Chrome extension recovers from local service `failed to fetch`.
- Helper starts the translation service on demand.
- Helper starts local Ollama when needed and allowed.
- Extension retries the original translation once after helper readiness.
- Service stops itself after configurable idle timeout when started in on-demand mode.
- Default idle timeout for helper-started service is 15 minutes.
- Default Ollama stop policy is `if-started-by-helper`.
- Helper installation is opt-in through `--install-chrome-helper`.
- Native Messaging host manifest is restricted to the configured extension ID.
- No arbitrary command execution is possible through helper messages.
- Existing always-on LaunchAgent service behavior remains available for users who install `--install-service`.
