# macOS On-Demand Chrome Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a macOS Chrome Native Messaging helper so the Chrome extension can start the local translation stack on demand, then let the HTTP service stop itself after configurable idle time.

**Architecture:** Chrome keeps normal HTTP translation as the first path. When local fetch fails at the network layer, `background.js` calls `sendNativeMessage()` to a macOS helper. The helper starts Ollama and the translate service when needed; the helper exits after one response, while the translate service owns idle shutdown.

**Tech Stack:** Python 3.11, Typer, FastAPI, uvicorn `Server`, httpx, Chrome Manifest V3 Native Messaging, macOS LaunchAgent/install scripts, plain JavaScript, pytest, ruff.

---

## File Structure

- Create `translate_service/chrome_helper.py`
  - Native Messaging framing, request validation, readiness checks, process start, helper state.
- Create `tests/test_chrome_helper.py`
  - Helper protocol, URL validation, process-start decision, and state-file tests.
- Create `tests/test_service_lifecycle.py`
  - Idle settings, activity middleware, graceful shutdown callback, and Ollama stop policy tests.
- Modify `pyproject.toml`
  - Add `local-translate-chrome-helper` console script.
- Modify `translate_service/cli.py`
  - Add `serve` idle shutdown and stop policy options.
- Modify `translate_service/api/app.py`
  - Track request activity and support idle lifecycle hooks.
- Modify `scripts/install_macos.sh`
  - Add `--install-chrome-helper` and `--chrome-extension-id`; generate Native Messaging host manifest.
- Modify `scripts/uninstall_macos.sh`
  - Remove Native Messaging host manifest if present.
- Modify `chrome_extension/manifest.json`
  - Add `nativeMessaging` permission.
- Modify `chrome_extension/background.js`
  - Retry network failures through helper.
- Modify `chrome_extension/options.html`
  - Add helper status, idle timeout, and Ollama stop policy controls.
- Modify `chrome_extension/options.js`
  - Store helper settings and test helper with `ping`.
- Modify `tests/test_chrome_extension.py`
  - Add static checks for native messaging and options controls.
- Modify `tests/test_macos_scripts.py`
  - Add installer/uninstaller Native Messaging checks.
- Modify `README.md` and `docs/handoff.md`
  - Document helper installation, lifecycle, and verification.

---

### Task 1: Native Messaging Helper Protocol

**Files:**
- Create: `translate_service/chrome_helper.py`
- Create: `tests/test_chrome_helper.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing helper protocol tests**

Create `tests/test_chrome_helper.py`:

```python
import io
import json
import struct
from pathlib import Path

import pytest

from translate_service import chrome_helper


ROOT = Path(__file__).resolve().parents[1]


def encode_frame(payload: dict[str, object]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return struct.pack("<I", len(body)) + body


def decode_frame(data: bytes) -> dict[str, object]:
    length = struct.unpack("<I", data[:4])[0]
    return json.loads(data[4 : 4 + length].decode("utf-8"))


def test_read_message_decodes_native_message_frame():
    stream = io.BytesIO(encode_frame({"type": "ping"}))

    assert chrome_helper.read_message(stream) == {"type": "ping"}


def test_write_message_encodes_native_message_frame():
    stream = io.BytesIO()

    chrome_helper.write_message(stream, {"ok": True, "type": "pong"})

    assert decode_frame(stream.getvalue()) == {"ok": True, "type": "pong"}


def test_read_message_rejects_oversized_frame():
    stream = io.BytesIO(struct.pack("<I", chrome_helper.MAX_MESSAGE_BYTES + 1))

    with pytest.raises(chrome_helper.HelperError, match="too large"):
        chrome_helper.read_message(stream)


def test_normalize_service_url_accepts_localhost_and_strips_slash():
    assert chrome_helper.normalize_service_url("http://127.0.0.1:8000/") == (
        "http://127.0.0.1:8000"
    )
    assert chrome_helper.normalize_service_url("http://localhost:8000") == (
        "http://localhost:8000"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8000",
        "http://example.com:8000",
        "http://user@127.0.0.1:8000",
        "http://127.0.0.1:8000/path",
        "http://127.0.0.1",
    ],
)
def test_normalize_service_url_rejects_unsafe_urls(url):
    with pytest.raises(chrome_helper.HelperError):
        chrome_helper.normalize_service_url(url)


def test_handle_ping_returns_pong(tmp_path):
    manager = chrome_helper.HelperManager(
        project_root=Path("/example/project"),
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
    )

    assert manager.handle_message({"type": "ping"}) == {"ok": True, "type": "pong"}


def test_handle_unknown_message_returns_error(tmp_path):
    manager = chrome_helper.HelperManager(
        project_root=Path("/example/project"),
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
    )

    response = manager.handle_message({"type": "unknown"})

    assert response["ok"] is False
    assert "Unsupported helper message" in response["error"]


def test_console_script_is_declared():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert (
        'local-translate-chrome-helper = "translate_service.chrome_helper:main"'
        in pyproject
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_chrome_helper.py -q
```

Expected: FAIL because `translate_service.chrome_helper` does not exist.

- [ ] **Step 3: Implement protocol, validation, and console script**

Create `translate_service/chrome_helper.py`:

```python
from __future__ import annotations

import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse


MAX_MESSAGE_BYTES = 64 * 1024
HELPER_NAME = "com.local.translate.helper"
DEFAULT_SERVICE_URL = "http://127.0.0.1:8000"
DEFAULT_STATE_PATH = (
    Path.home() / "Library" / "Application Support" / "LocalTranslate" / "helper-state.json"
)
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "translate-service"


class HelperError(Exception):
    """User-facing helper failure."""


def read_message(stream: BinaryIO) -> dict[str, object]:
    header = stream.read(4)
    if len(header) != 4:
        raise HelperError("No native message header was received.")
    length = struct.unpack("<I", header)[0]
    if length > MAX_MESSAGE_BYTES:
        raise HelperError(f"Native message is too large: {length} bytes.")
    body = stream.read(length)
    if len(body) != length:
        raise HelperError("Native message body was incomplete.")
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HelperError("Native message body must be UTF-8 JSON.") from exc
    if not isinstance(message, dict):
        raise HelperError("Native message must be a JSON object.")
    return message


def write_message(stream: BinaryIO, message: dict[str, object]) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack("<I", len(body)))
    stream.write(body)
    stream.flush()


def normalize_service_url(value: object) -> str:
    raw = str(value or DEFAULT_SERVICE_URL).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "http":
        raise HelperError("Service URL must use http.")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise HelperError("Service URL must point to 127.0.0.1 or localhost.")
    if parsed.username or parsed.password:
        raise HelperError("Service URL must not include credentials.")
    if parsed.path not in {"", "/"}:
        raise HelperError("Service URL must not include a path.")
    if parsed.params or parsed.query or parsed.fragment:
        raise HelperError("Service URL must not include params, query, or fragment.")
    if parsed.port is None:
        raise HelperError("Service URL must include a port.")
    return f"http://{parsed.hostname}:{parsed.port}"


@dataclass
class HelperManager:
    project_root: Path
    state_path: Path = DEFAULT_STATE_PATH
    log_dir: Path = DEFAULT_LOG_DIR

    def handle_message(self, message: dict[str, object]) -> dict[str, object]:
        try:
            message_type = message.get("type")
            if message_type == "ping":
                return {"ok": True, "type": "pong"}
            if message_type == "ensure_ready":
                return self.ensure_ready(message)
            raise HelperError(f"Unsupported helper message: {message_type!r}.")
        except HelperError as exc:
            return {"ok": False, "error": str(exc)}

    def ensure_ready(self, message: dict[str, object]) -> dict[str, object]:
        service_url = normalize_service_url(message.get("service_url", DEFAULT_SERVICE_URL))
        return {
            "ok": True,
            "type": "ready",
            "service_url": service_url,
            "ollama_started": False,
            "translate_started": False,
        }


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> None:
    manager = HelperManager(project_root=default_project_root())
    try:
        message = read_message(sys.stdin.buffer)
        response = manager.handle_message(message)
    except HelperError as exc:
        response = {"ok": False, "error": str(exc)}
    write_message(sys.stdout.buffer, response)
```

Modify `pyproject.toml`:

```toml
[project.scripts]
translate = "translate_service.cli:app"
local-translate-chrome-helper = "translate_service.chrome_helper:main"
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_chrome_helper.py -q
```

Expected: PASS.

- [ ] **Step 5: Run linter**

Run:

```bash
.venv/bin/ruff check translate_service/chrome_helper.py tests/test_chrome_helper.py pyproject.toml
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add pyproject.toml translate_service/chrome_helper.py tests/test_chrome_helper.py
git commit -m "feat: add chrome native helper protocol"
```

---

### Task 2: Helper Readiness and Process Start

**Files:**
- Modify: `translate_service/chrome_helper.py`
- Modify: `tests/test_chrome_helper.py`

- [ ] **Step 1: Add failing helper process tests**

Append to `tests/test_chrome_helper.py`:

```python
class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid


def test_ensure_ready_starts_ollama_and_translate_when_unreachable(tmp_path):
    events: list[str] = []

    def fake_get_json(url: str, timeout_seconds: float = 2.0):
        events.append(f"check:{url}")
        raise chrome_helper.HelperError("not reachable")

    def fake_sleep(_seconds: float):
        events.append("sleep")

    def fake_popen(args, **_kwargs):
        events.append("start:" + " ".join(str(part) for part in args[:2]))
        return FakeProcess(222 if args[0] == "ollama" else 333)

    manager = chrome_helper.HelperManager(
        project_root=ROOT,
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
        get_json=fake_get_json,
        popen=fake_popen,
        which=lambda name: name if name == "ollama" else None,
        sleep=fake_sleep,
        ready_timeout_seconds=0,
    )

    response = manager.handle_message(
        {
            "type": "ensure_ready",
            "service_url": "http://127.0.0.1:8000",
            "idle_timeout_seconds": 900,
            "stop_ollama_policy": "if-started-by-helper",
        }
    )

    assert response["ok"] is False
    assert "did not become ready" in response["error"]
    assert "start:ollama serve" in events
    assert any(event.startswith(f"start:{ROOT / '.venv' / 'bin' / 'translate'}") for event in events)


def test_ensure_ready_returns_ready_without_starting_when_health_reachable(tmp_path):
    def fake_get_json(url: str, timeout_seconds: float = 2.0):
        if url.endswith("/api/tags"):
            return {"models": []}
        if url.endswith("/health"):
            return {"status": "ok"}
        raise AssertionError(url)

    starts = []
    manager = chrome_helper.HelperManager(
        project_root=ROOT,
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
        get_json=fake_get_json,
        popen=lambda args, **kwargs: starts.append(args),
        which=lambda name: name if name == "ollama" else None,
    )

    response = manager.handle_message(
        {"type": "ensure_ready", "service_url": "http://127.0.0.1:8000"}
    )

    assert response == {
        "ok": True,
        "type": "ready",
        "service_url": "http://127.0.0.1:8000",
        "ollama_started": False,
        "translate_started": False,
    }
    assert starts == []


def test_helper_writes_state_when_it_starts_processes(tmp_path):
    health_checks = 0

    def fake_get_json(url: str, timeout_seconds: float = 2.0):
        nonlocal health_checks
        if url.endswith("/api/tags"):
            raise chrome_helper.HelperError("ollama down")
        if url.endswith("/health"):
            health_checks += 1
            if health_checks == 1:
                raise chrome_helper.HelperError("service down")
            return {"status": "ok"}
        raise AssertionError(url)

    def fake_popen(args, **_kwargs):
        return FakeProcess(222 if args[0] == "ollama" else 333)

    state_path = tmp_path / "helper-state.json"
    manager = chrome_helper.HelperManager(
        project_root=ROOT,
        state_path=state_path,
        log_dir=tmp_path,
        get_json=fake_get_json,
        popen=fake_popen,
        which=lambda name: name if name == "ollama" else None,
        sleep=lambda _seconds: None,
        ready_timeout_seconds=2,
    )

    response = manager.handle_message(
        {"type": "ensure_ready", "service_url": "http://127.0.0.1:8000"}
    )

    assert response["ok"] is True
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["translate_pid"] == 333
    assert state["ollama_pid"] == 222
    assert state["ollama_started_by_helper"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_chrome_helper.py -q
```

Expected: FAIL because `HelperManager` does not accept dependency injection and does not start processes.

- [ ] **Step 3: Implement readiness checks and process start**

Modify `translate_service/chrome_helper.py` by adding imports:

```python
import shutil
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
```

Add helpers:

```python
STOP_POLICIES = {"never", "if-started-by-helper", "always"}


def validate_idle_timeout(value: object) -> int:
    if value is None:
        return 900
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise HelperError("idle_timeout_seconds must be an integer.") from exc
    if timeout < 0:
        raise HelperError("idle_timeout_seconds must be greater than or equal to 0.")
    return timeout


def validate_stop_policy(value: object) -> str:
    policy = str(value or "if-started-by-helper")
    if policy not in STOP_POLICIES:
        raise HelperError(f"Unsupported stop_ollama_policy: {policy}.")
    return policy


def default_get_json(url: str, timeout_seconds: float = 2.0) -> dict[str, Any]:
    try:
        response = httpx.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise HelperError(f"{url} is not reachable.") from exc
    if not isinstance(data, dict):
        raise HelperError(f"{url} returned a non-object JSON response.")
    return data
```

Change `HelperManager` fields:

```python
@dataclass
class HelperManager:
    project_root: Path
    state_path: Path = DEFAULT_STATE_PATH
    log_dir: Path = DEFAULT_LOG_DIR
    get_json: Callable[[str, float], dict[str, Any]] = default_get_json
    popen: Callable[..., Any] = subprocess.Popen
    which: Callable[[str], str | None] = shutil.which
    sleep: Callable[[float], None] = time.sleep
    ready_timeout_seconds: int = 30
```

Replace `ensure_ready`:

```python
    def ensure_ready(self, message: dict[str, object]) -> dict[str, object]:
        service_url = normalize_service_url(message.get("service_url", DEFAULT_SERVICE_URL))
        idle_timeout_seconds = validate_idle_timeout(message.get("idle_timeout_seconds"))
        stop_policy = validate_stop_policy(message.get("stop_ollama_policy"))

        ollama_started = self.ensure_ollama()
        translate_started = self.ensure_translate_service(
            service_url=service_url,
            idle_timeout_seconds=idle_timeout_seconds,
            stop_policy=stop_policy,
            ollama_started=ollama_started,
        )
        self.wait_for_health(service_url)
        return {
            "ok": True,
            "type": "ready",
            "service_url": service_url,
            "ollama_started": ollama_started,
            "translate_started": translate_started,
        }
```

Add methods:

```python
    def ensure_ollama(self) -> bool:
        try:
            self.get_json("http://127.0.0.1:11434/api/tags", 2.0)
            return False
        except HelperError:
            ollama_bin = self.which("ollama")
            if not ollama_bin:
                raise HelperError("Ollama is not installed or is not on PATH.")
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = (self.log_dir / "ollama.log").open("ab")
            process = self.popen(
                [ollama_bin, "serve"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.write_state({"ollama_pid": getattr(process, "pid", None), "ollama_started_by_helper": True})
            return True

    def ensure_translate_service(
        self,
        *,
        service_url: str,
        idle_timeout_seconds: int,
        stop_policy: str,
        ollama_started: bool,
    ) -> bool:
        try:
            self.get_json(f"{service_url}/health", 2.0)
            return False
        except HelperError:
            parsed = urlparse(service_url)
            translate_bin = self.project_root / ".venv" / "bin" / "translate"
            if not translate_bin.exists():
                raise HelperError(f"Translate executable not found at {translate_bin}.")
            self.log_dir.mkdir(parents=True, exist_ok=True)
            stdout = (self.log_dir / "stdout.log").open("ab")
            stderr = (self.log_dir / "stderr.log").open("ab")
            process = self.popen(
                [
                    str(translate_bin),
                    "serve",
                    "--host",
                    str(parsed.hostname),
                    "--port",
                    str(parsed.port),
                    "--idle-timeout-seconds",
                    str(idle_timeout_seconds),
                    "--stop-ollama-policy",
                    stop_policy,
                ],
                cwd=self.project_root,
                stdout=stdout,
                stderr=stderr,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.write_state(
                {
                    "translate_pid": getattr(process, "pid", None),
                    "ollama_started_by_helper": ollama_started,
                    "service_url": service_url,
                    "started_at": datetime.now(UTC).isoformat(),
                }
            )
            return True

    def wait_for_health(self, service_url: str) -> None:
        deadline = time.monotonic() + self.ready_timeout_seconds
        while time.monotonic() <= deadline:
            try:
                self.get_json(f"{service_url}/health", 2.0)
                return
            except HelperError:
                self.sleep(1)
        raise HelperError(
            f"Translation service did not become ready within {self.ready_timeout_seconds} seconds."
        )

    def write_state(self, updates: dict[str, object]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state: dict[str, object] = {}
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
        state.update({key: value for key, value in updates.items() if value is not None})
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_chrome_helper.py -q
```

Expected: PASS.

- [ ] **Step 5: Run linter**

Run:

```bash
.venv/bin/ruff check translate_service/chrome_helper.py tests/test_chrome_helper.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add translate_service/chrome_helper.py tests/test_chrome_helper.py
git commit -m "feat: start local services from chrome helper"
```

---

### Task 3: On-Demand Service Idle Lifecycle

**Files:**
- Create: `tests/test_service_lifecycle.py`
- Modify: `translate_service/api/app.py`
- Modify: `translate_service/cli.py`

- [ ] **Step 1: Write failing lifecycle tests**

Create `tests/test_service_lifecycle.py`:

```python
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from translate_service.api.app import StopOllamaPolicy, create_app
from translate_service.cli import app as cli_app


class FakeService:
    async def translate(self, *, text: str, source_lang=None, target_lang=None):
        return {
            "translation": text,
            "source_lang": {"code": source_lang or "en", "name": "English"},
            "target_lang": {"code": target_lang or "zh", "name": "Chinese"},
            "model": "translategemma:latest",
        }

    async def health(self):
        return {"status": "ok"}


def test_app_tracks_activity_for_requests():
    app = create_app(FakeService(), idle_timeout_seconds=60)
    before = app.state.last_activity_at
    time.sleep(0.001)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert app.state.last_activity_at > before


def test_app_defaults_idle_shutdown_disabled():
    app = create_app(FakeService())

    assert app.state.idle_timeout_seconds == 0
    assert app.state.stop_ollama_policy == StopOllamaPolicy.NEVER


def test_should_stop_for_idle_timeout():
    app = create_app(FakeService(), idle_timeout_seconds=1)
    app.state.last_activity_at = time.monotonic() - 2

    assert app.state.should_stop_for_idle_timeout() is True


def test_stop_ollama_if_started_by_helper_requires_state(tmp_path):
    state_path = tmp_path / "helper-state.json"
    state_path.write_text(
        json.dumps({"ollama_started_by_helper": True, "ollama_pid": 12345}),
        encoding="utf-8",
    )
    stopped: list[int] = []
    app = create_app(
        FakeService(),
        stop_ollama_policy=StopOllamaPolicy.IF_STARTED_BY_HELPER,
        helper_state_path=state_path,
        stop_pid=stopped.append,
    )

    app.state.stop_ollama_if_needed()

    assert stopped == [12345]
    assert not state_path.exists()


def test_stop_ollama_if_started_by_helper_leaves_missing_pid_running(tmp_path):
    state_path = tmp_path / "helper-state.json"
    state_path.write_text(json.dumps({"ollama_started_by_helper": True}), encoding="utf-8")
    stopped: list[int] = []
    app = create_app(
        FakeService(),
        stop_ollama_policy=StopOllamaPolicy.IF_STARTED_BY_HELPER,
        helper_state_path=state_path,
        stop_pid=stopped.append,
    )

    app.state.stop_ollama_if_needed()

    assert stopped == []
    assert not state_path.exists()


def test_cli_serve_exposes_idle_options():
    command = cli_app.registered_commands[-1]
    callback = command.callback

    assert "idle_timeout_seconds" in callback.__annotations__
    assert "stop_ollama_policy" in callback.__annotations__
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_service_lifecycle.py -q
```

Expected: FAIL because `StopOllamaPolicy` and idle lifecycle options do not exist.

- [ ] **Step 3: Add lifecycle state to FastAPI app**

Modify `translate_service/api/app.py` imports:

```python
import asyncio
import json
import os
import signal
import time
from collections.abc import Callable
from enum import StrEnum
```

Add:

```python
HELPER_STATE_PATH = (
    Path.home() / "Library" / "Application Support" / "LocalTranslate" / "helper-state.json"
)


class StopOllamaPolicy(StrEnum):
    NEVER = "never"
    IF_STARTED_BY_HELPER = "if-started-by-helper"
    ALWAYS = "always"


def stop_pid_with_sigterm(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)
```

Change `create_app` signature:

```python
def create_app(
    service: TranslationService | None = None,
    *,
    idle_timeout_seconds: int = 0,
    stop_ollama_policy: StopOllamaPolicy = StopOllamaPolicy.NEVER,
    helper_state_path: Path = HELPER_STATE_PATH,
    stop_pid: Callable[[int], None] = stop_pid_with_sigterm,
    on_idle_timeout: Callable[[], None] | None = None,
) -> FastAPI:
```

Inside `create_app`, after `app.state.translation_service = service`, add:

```python
    app.state.idle_timeout_seconds = idle_timeout_seconds
    app.state.stop_ollama_policy = stop_ollama_policy
    app.state.helper_state_path = helper_state_path
    app.state.stop_pid = stop_pid
    app.state.last_activity_at = time.monotonic()

    def should_stop_for_idle_timeout() -> bool:
        if app.state.idle_timeout_seconds <= 0:
            return False
        idle_for = time.monotonic() - app.state.last_activity_at
        return idle_for >= app.state.idle_timeout_seconds

    def stop_ollama_if_needed() -> None:
        policy = app.state.stop_ollama_policy
        state_path = app.state.helper_state_path
        if policy == StopOllamaPolicy.NEVER:
            return
        state = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
        pid = state.get("ollama_pid")
        started_by_helper = bool(state.get("ollama_started_by_helper"))
        should_stop = policy == StopOllamaPolicy.ALWAYS or (
            policy == StopOllamaPolicy.IF_STARTED_BY_HELPER and started_by_helper and isinstance(pid, int)
        )
        if should_stop and isinstance(pid, int):
            app.state.stop_pid(pid)
        if state_path.exists():
            state_path.unlink()

    app.state.should_stop_for_idle_timeout = should_stop_for_idle_timeout
    app.state.stop_ollama_if_needed = stop_ollama_if_needed

    @app.middleware("http")
    async def track_activity(request: Request, call_next):
        app.state.last_activity_at = time.monotonic()
        return await call_next(request)
```

Add startup idle monitor only when `on_idle_timeout` is provided:

```python
    async def idle_monitor():
        while True:
            await asyncio.sleep(1)
            if app.state.should_stop_for_idle_timeout():
                app.state.stop_ollama_if_needed()
                if on_idle_timeout is not None:
                    on_idle_timeout()
                return

    if idle_timeout_seconds > 0 and on_idle_timeout is not None:
        @app.on_event("startup")
        async def start_idle_monitor():
            app.state.idle_monitor_task = asyncio.create_task(idle_monitor())
```

- [ ] **Step 4: Update CLI serve to use uvicorn Server**

Modify `translate_service/cli.py` imports:

```python
from typing import Annotated
```

Modify `serve`:

```python
@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    idle_timeout_seconds: Annotated[int, typer.Option("--idle-timeout-seconds")] = 0,
    stop_ollama_policy: Annotated[
        str,
        typer.Option("--stop-ollama-policy"),
    ] = "never",
):
    import uvicorn

    from translate_service.api.app import StopOllamaPolicy, create_app

    policy = StopOllamaPolicy(stop_ollama_policy)
    server: uvicorn.Server | None = None

    def request_shutdown() -> None:
        if server is not None:
            server.should_exit = True

    server = uvicorn.Server(
        uvicorn.Config(
            create_app(
                idle_timeout_seconds=idle_timeout_seconds,
                stop_ollama_policy=policy,
                on_idle_timeout=request_shutdown,
            ),
            host=host,
            port=port,
        )
    )
    server.run()
```

- [ ] **Step 5: Run lifecycle tests**

Run:

```bash
.venv/bin/pytest tests/test_service_lifecycle.py -q
```

Expected: PASS.

- [ ] **Step 6: Run existing API and CLI tests**

Run:

```bash
.venv/bin/pytest tests/test_api.py tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Run linter**

Run:

```bash
.venv/bin/ruff check translate_service/api/app.py translate_service/cli.py tests/test_service_lifecycle.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add translate_service/api/app.py translate_service/cli.py tests/test_service_lifecycle.py
git commit -m "feat: add idle shutdown lifecycle"
```

---

### Task 4: macOS Installer Native Messaging Registration

**Files:**
- Modify: `scripts/install_macos.sh`
- Modify: `scripts/uninstall_macos.sh`
- Modify: `tests/test_macos_scripts.py`

- [ ] **Step 1: Write failing installer tests**

Append to `tests/test_macos_scripts.py`:

```python
def test_install_script_exposes_chrome_helper_options():
    script = read_script(INSTALL_SCRIPT)

    assert "--install-chrome-helper" in script
    assert "--chrome-extension-id" in script
    assert "NativeMessagingHosts" in script
    assert "com.local.translate.helper.json" in script
    assert "local-translate-chrome-helper" in script


def test_install_script_validates_chrome_extension_id():
    script = read_script(INSTALL_SCRIPT)

    assert "validate_chrome_extension_id()" in script
    assert "Chrome extension ID must contain 32 lowercase letters" in script
    assert '[ "$INSTALL_CHROME_HELPER" -eq 1 ]' in script
    assert 'validate_chrome_extension_id "$CHROME_EXTENSION_ID"' in script


def test_install_script_generates_native_messaging_manifest_with_json():
    script = read_script(INSTALL_SCRIPT)

    assert "import json" in script
    assert '"allowed_origins"' in script
    assert '"chrome-extension://" + extension_id + "/"' in script
    assert '"type": "stdio"' in script


def test_uninstall_script_removes_chrome_helper_manifest():
    script = read_script(UNINSTALL_SCRIPT)

    assert "com.local.translate.helper.json" in script
    assert "NativeMessagingHosts" in script
    assert "Removed Chrome Native Messaging helper manifest" in script
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py -q
```

Expected: FAIL because helper options are not implemented.

- [ ] **Step 3: Modify install script**

In `scripts/install_macos.sh`, add variables near current option variables:

```bash
INSTALL_CHROME_HELPER=0
CHROME_EXTENSION_ID=""
NATIVE_HOST_NAME="com.local.translate.helper"
NATIVE_HOST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
NATIVE_HOST_PATH="$NATIVE_HOST_DIR/$NATIVE_HOST_NAME.json"
```

Add usage lines:

```text
  --install-chrome-helper      Install Chrome Native Messaging helper manifest.
  --chrome-extension-id ID     Chrome extension ID allowed to call the helper.
```

Add argument parsing:

```bash
    --install-chrome-helper) INSTALL_CHROME_HELPER=1; shift ;;
    --chrome-extension-id) CHROME_EXTENSION_ID="${2:-}"; [ -n "$CHROME_EXTENSION_ID" ] || die "--chrome-extension-id requires a value"; shift 2 ;;
```

Add validator:

```bash
validate_chrome_extension_id() {
  value="$1"
  case "$value" in
    [a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z][a-z])
      ;;
    *)
      die "Chrome extension ID must contain 32 lowercase letters."
      ;;
  esac
}
```

After editable install, add:

```bash
if [ "$INSTALL_CHROME_HELPER" -eq 1 ]; then
  log "Installing Chrome Native Messaging helper"
  validate_chrome_extension_id "$CHROME_EXTENSION_ID"
  HELPER_BIN="$VENV_DIR/bin/local-translate-chrome-helper"
  [ -x "$HELPER_BIN" ] || die "Chrome helper executable not found at $HELPER_BIN"
  mkdir -p "$NATIVE_HOST_DIR"
  "$VENV_DIR/bin/python" - "$NATIVE_HOST_PATH" "$NATIVE_HOST_NAME" "$HELPER_BIN" "$CHROME_EXTENSION_ID" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, host_name, helper_bin, extension_id = sys.argv[1:]
manifest = {
    "name": host_name,
    "description": "Local Translate on-demand service helper",
    "path": helper_bin,
    "type": "stdio",
    "allowed_origins": ["chrome-extension://" + extension_id + "/"],
}
Path(manifest_path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
PY
  log "Installed Chrome Native Messaging helper manifest at $NATIVE_HOST_PATH"
fi
```

- [ ] **Step 4: Modify uninstall script**

In `scripts/uninstall_macos.sh`, add:

```bash
NATIVE_HOST_PATH="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.local.translate.helper.json"
```

After LaunchAgent removal:

```bash
if [ -f "$NATIVE_HOST_PATH" ]; then
  rm -f "$NATIVE_HOST_PATH"
  log "Removed Chrome Native Messaging helper manifest at $NATIVE_HOST_PATH"
else
  log "No Chrome Native Messaging helper manifest found at $NATIVE_HOST_PATH"
fi
```

- [ ] **Step 5: Run installer tests and shell syntax checks**

Run:

```bash
.venv/bin/pytest tests/test_macos_scripts.py -q
bash -n scripts/install_macos.sh
bash -n scripts/uninstall_macos.sh
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/install_macos.sh scripts/uninstall_macos.sh tests/test_macos_scripts.py
git commit -m "feat: register macos chrome helper"
```

---

### Task 5: Extension Native Helper Retry Flow

**Files:**
- Modify: `chrome_extension/manifest.json`
- Modify: `chrome_extension/background.js`
- Modify: `tests/test_chrome_extension.py`

- [ ] **Step 1: Add failing extension static tests**

Append to `tests/test_chrome_extension.py`:

```python
def test_manifest_allows_native_messaging():
    manifest = read_manifest()

    assert "nativeMessaging" in manifest["permissions"]


def test_background_retries_fetch_through_native_helper():
    background = (EXTENSION_DIR / "background.js").read_text(encoding="utf-8")

    assert "chrome.runtime.sendNativeMessage" in background
    assert "com.local.translate.helper" in background
    assert "ensure_ready" in background
    assert "retryAfterHelper" in background
    assert "Local service is not running and the Chrome helper is not installed." in background
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py -q
```

Expected: FAIL because native messaging is not implemented.

- [ ] **Step 3: Add manifest permission**

Modify `chrome_extension/manifest.json` permissions:

```json
"permissions": ["contextMenus", "storage", "activeTab", "scripting", "nativeMessaging"]
```

- [ ] **Step 4: Add helper retry flow to background**

In `chrome_extension/background.js`, add constants:

```javascript
const NATIVE_HELPER_NAME = "com.local.translate.helper";
const DEFAULT_IDLE_TIMEOUT_MINUTES = 15;
const DEFAULT_STOP_OLLAMA_POLICY = "if-started-by-helper";
```

Extend `DEFAULT_SETTINGS`:

```javascript
  idleTimeoutMinutes: DEFAULT_IDLE_TIMEOUT_MINUTES,
  stopOllamaPolicy: DEFAULT_STOP_OLLAMA_POLICY,
```

Add helpers:

```javascript
function isNetworkFailure(error) {
  return error instanceof TypeError || /Failed to fetch|NetworkError/i.test(error?.message || "");
}

function runtimeErrorMessage() {
  return chrome.runtime.lastError ? chrome.runtime.lastError.message : "";
}

function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(NATIVE_HELPER_NAME, message, (response) => {
      const error = runtimeErrorMessage();
      if (error) {
        reject(new Error("Local service is not running and the Chrome helper is not installed."));
        return;
      }
      if (!response || response.ok === false) {
        reject(new Error(response?.error || "Chrome helper could not start the local service."));
        return;
      }
      resolve(response);
    });
  });
}

async function ensureReadyWithHelper(settings) {
  return sendNativeMessage({
    type: "ensure_ready",
    service_url: settings.serviceUrl,
    idle_timeout_seconds: Math.max(0, Number(settings.idleTimeoutMinutes || 15)) * 60,
    stop_ollama_policy: settings.stopOllamaPolicy || DEFAULT_STOP_OLLAMA_POLICY,
  });
}
```

Change `requestJson` signature and catch:

```javascript
async function requestJson(path, options = {}, retryAfterHelper = true) {
  const settings = await getSettings();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${settings.serviceUrl}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const message = await parseApiError(response);
      throw new Error(message || `Request failed with status ${response.status}.`);
    }
    return response.json();
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        `Local translation timed out after ${REQUEST_TIMEOUT_SECONDS} seconds. Try shorter text or check Ollama.`,
      );
    }
    if (retryAfterHelper && isNetworkFailure(error)) {
      await ensureReadyWithHelper(settings);
      return requestJson(path, options, false);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
```

- [ ] **Step 5: Run extension tests and JS syntax**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py -q
node --check chrome_extension/background.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add chrome_extension/manifest.json chrome_extension/background.js tests/test_chrome_extension.py
git commit -m "feat: retry extension requests through native helper"
```

---

### Task 6: Extension Options for Helper Settings

**Files:**
- Modify: `chrome_extension/options.html`
- Modify: `chrome_extension/options.js`
- Modify: `tests/test_chrome_extension.py`

- [ ] **Step 1: Add failing options tests**

Append to `tests/test_chrome_extension.py`:

```python
def test_options_exposes_helper_lifecycle_controls():
    html = (EXTENSION_DIR / "options.html").read_text(encoding="utf-8")
    js = (EXTENSION_DIR / "options.js").read_text(encoding="utf-8")

    for expected in [
        'id="testHelperButton"',
        'id="helperStatus"',
        'id="idleTimeoutMinutes"',
        'id="stopOllamaPolicy"',
    ]:
        assert expected in html
    assert "LOCAL_TRANSLATE_TEST_HELPER" in js
    assert "idleTimeoutMinutes" in js
    assert "stopOllamaPolicy" in js
    assert "if-started-by-helper" in js
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py::test_options_exposes_helper_lifecycle_controls -q
```

Expected: FAIL because controls do not exist.

- [ ] **Step 3: Add options HTML controls**

Modify `chrome_extension/options.html` after target language:

```html
      <label>
        Idle timeout minutes
        <input id="idleTimeoutMinutes" type="number" min="0" step="1" />
      </label>
      <label>
        Stop Ollama
        <select id="stopOllamaPolicy">
          <option value="never">Never</option>
          <option value="if-started-by-helper">If started by helper</option>
          <option value="always">Always</option>
        </select>
      </label>
```

Add button and status:

```html
        <button id="testHelperButton" type="button">Test helper</button>
```

Add below message:

```html
      <p id="helperStatus" class="message" role="status" aria-live="polite"></p>
```

- [ ] **Step 4: Add options JS settings and helper test**

Modify `DEFAULT_SETTINGS`:

```javascript
  idleTimeoutMinutes: 15,
  stopOllamaPolicy: "if-started-by-helper",
```

Add elements:

```javascript
  idleTimeoutMinutes: document.querySelector("#idleTimeoutMinutes"),
  stopOllamaPolicy: document.querySelector("#stopOllamaPolicy"),
  testHelperButton: document.querySelector("#testHelperButton"),
  helperStatus: document.querySelector("#helperStatus"),
```

Add:

```javascript
function setHelperStatus(text, type = "") {
  elements.helperStatus.textContent = text;
  elements.helperStatus.className = `message ${type}`.trim();
}

function normalizeIdleTimeout(value) {
  const minutes = Number.parseInt(String(value || "15"), 10);
  if (!Number.isFinite(minutes) || minutes < 0) {
    throw new Error("Idle timeout must be zero or greater.");
  }
  return minutes;
}

function normalizeStopPolicy(value) {
  const policy = String(value || DEFAULT_SETTINGS.stopOllamaPolicy);
  if (!["never", "if-started-by-helper", "always"].includes(policy)) {
    throw new Error("Choose a valid Ollama stop policy.");
  }
  return policy;
}

function sendMessage(message) {
  return chrome.runtime.sendMessage(message);
}
```

In `loadSettings`:

```javascript
  elements.idleTimeoutMinutes.value = settings.idleTimeoutMinutes;
  elements.stopOllamaPolicy.value = settings.stopOllamaPolicy;
```

In `saveSettings`:

```javascript
      idleTimeoutMinutes: normalizeIdleTimeout(elements.idleTimeoutMinutes.value),
      stopOllamaPolicy: normalizeStopPolicy(elements.stopOllamaPolicy.value),
```

In `resetSettings`:

```javascript
  elements.idleTimeoutMinutes.value = settings.idleTimeoutMinutes;
  elements.stopOllamaPolicy.value = settings.stopOllamaPolicy;
```

Add:

```javascript
async function testHelper() {
  try {
    const response = await sendMessage({ type: "LOCAL_TRANSLATE_TEST_HELPER" });
    if (!response.ok) {
      throw new Error(response.error || "Chrome helper did not respond.");
    }
    setHelperStatus("Chrome helper is available.", "success");
  } catch (error) {
    setHelperStatus(`Chrome helper check failed: ${error.message}`, "error");
  }
}
```

Bind:

```javascript
  elements.testHelperButton.addEventListener("click", testHelper);
```

- [ ] **Step 5: Add background message for helper ping**

In `chrome_extension/background.js` message listener add:

```javascript
  if (message?.type === "LOCAL_TRANSLATE_TEST_HELPER") {
    sendNativeMessage({ type: "ping" })
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
```

- [ ] **Step 6: Run tests and JS syntax**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py -q
node --check chrome_extension/background.js
node --check chrome_extension/options.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add chrome_extension/background.js chrome_extension/options.html chrome_extension/options.js tests/test_chrome_extension.py
git commit -m "feat: add helper lifecycle options"
```

---

### Task 7: Documentation and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/handoff.md`

- [ ] **Step 1: Update README**

Add to the Chrome Extension section:

```markdown
### On-Demand macOS Helper

On macOS, the extension can start the local service on demand through a Chrome
Native Messaging helper.

Load the extension first, copy its Chrome extension ID, then run:

```bash
scripts/install_macos.sh --install-chrome-helper --chrome-extension-id EXTENSION_ID
```

The helper starts the translate HTTP service when the extension cannot reach
`http://127.0.0.1:8000`. It can also start local Ollama when Ollama is installed
but not running. The helper does not install Ollama or pull models.

The helper-started HTTP service stops itself after the configured idle timeout.
The default is 15 minutes. By default, Ollama is stopped only when the helper
started it and recorded its PID.
```

- [ ] **Step 2: Update handoff**

Add to `docs/handoff.md`:

```markdown
## macOS On-Demand Chrome Helper

The Chrome extension can use a macOS Native Messaging helper named
`com.local.translate.helper` to recover from local service `failed to fetch`.

Install helper registration explicitly:

```bash
scripts/install_macos.sh --install-chrome-helper --chrome-extension-id EXTENSION_ID
```

The helper starts the local stack and exits after one response. Idle shutdown is
owned by the translate HTTP service through `--idle-timeout-seconds`.
```

- [ ] **Step 3: Run full tests**

Run:

```bash
.venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 4: Run linter**

Run:

```bash
.venv/bin/ruff check .
```

Expected: PASS.

- [ ] **Step 5: Run JS syntax checks**

Run:

```bash
node --check chrome_extension/background.js
node --check chrome_extension/options.js
```

Expected: PASS.

- [ ] **Step 6: Run shell syntax checks**

Run:

```bash
bash -n scripts/install_macos.sh
bash -n scripts/uninstall_macos.sh
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add README.md docs/handoff.md
git commit -m "docs: document macos on-demand chrome helper"
```

---

## Manual Verification Checklist

Run after all tasks:

```bash
.venv/bin/pip install -e .
```

Then:

1. Load `chrome_extension/` unpacked in Chrome.
2. Copy the extension ID.
3. Run:
   ```bash
   scripts/install_macos.sh --install-chrome-helper --chrome-extension-id EXTENSION_ID
   ```
4. Stop any manually running translate service.
5. Stop Ollama if testing cold start.
6. Select text in Chrome and choose **Translate selection locally**.
7. Confirm the extension starts the service and retries translation.
8. Confirm `~/Library/Application Support/LocalTranslate/helper-state.json` is written when processes are started.
9. Set idle timeout to 1 minute in extension options for testing.
10. Wait for idle timeout and confirm the translate service exits.
11. Confirm Ollama stop behavior matches the selected policy.

---

## Self-Review

- Spec coverage: Plan covers helper protocol, process start, idle shutdown, installer/uninstaller, extension retry, options controls, docs, and verification.
- Scope: macOS only; Linux and Windows helper support remain out of scope.
- Safety: No arbitrary command execution; helper validates local URLs and restricted message types.
- Defaults: Idle timeout is 15 minutes for helper-started service; ordinary CLI service keeps idle shutdown disabled.
- Native Messaging constraint: Manifest uses an absolute console-script executable path, not a command with arguments.
