from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, Callable
from urllib.parse import urlparse

import httpx

MAX_MESSAGE_BYTES = 64 * 1024
HELPER_NAME = "com.local.translate.helper"
DEFAULT_SERVICE_URL = "http://127.0.0.1:8000"
DEFAULT_IDLE_TIMEOUT_SECONDS = 900
DEFAULT_STOP_POLICY = "if-started-by-helper"
STOP_POLICIES = {"never", "if-started-by-helper", "always"}
DEFAULT_STATE_PATH = (
    Path.home() / "Library" / "Application Support" / "LocalTranslate" / "helper-state.json"
)
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "translate-service"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
STATE_ERROR = "Could not write helper state."


class HelperError(Exception):
    pass


def read_message(stream: BinaryIO) -> dict[str, object]:
    header = stream.read(4)
    if len(header) != 4:
        raise HelperError("Missing native messaging frame header")

    (message_size,) = struct.unpack("<I", header)
    if message_size > MAX_MESSAGE_BYTES:
        raise HelperError(f"Native messaging frame is too large: {message_size} bytes")

    payload = stream.read(message_size)
    if len(payload) != message_size:
        raise HelperError("Incomplete native messaging frame payload")

    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HelperError(f"Invalid native messaging JSON: {exc}") from exc

    if not isinstance(message, dict):
        raise HelperError("Native messaging payload must be an object")
    return message


def write_message(stream: BinaryIO, message: dict[str, object]) -> None:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise HelperError(f"Native messaging response is too large: {len(payload)} bytes")

    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()


def normalize_service_url(value: object) -> str:
    if not isinstance(value, str):
        raise HelperError("service_url must be a string")

    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise HelperError("Service URL is invalid.") from exc
    if parsed.scheme != "http":
        raise HelperError("service_url must use http")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise HelperError("service_url must point to localhost")
    if parsed.username or parsed.password:
        raise HelperError("service_url must not include credentials")

    try:
        port = parsed.port
    except ValueError as exc:
        raise HelperError("Service URL must include a valid port.") from exc
    if port is None:
        raise HelperError("service_url must include a port")
    if port < 1:
        raise HelperError("service_url must include a valid port")
    if parsed.path not in {"", "/"}:
        raise HelperError("service_url must not include a path")
    if parsed.params or parsed.query or parsed.fragment:
        raise HelperError("service_url must not include params, query, or fragment")

    return f"http://{parsed.hostname}:{port}"


def validate_idle_timeout(value: object) -> int:
    if value is None:
        return DEFAULT_IDLE_TIMEOUT_SECONDS
    if isinstance(value, bool) or not isinstance(value, int):
        raise HelperError("idle_timeout_seconds must be a non-negative integer")
    if value < 0:
        raise HelperError("idle_timeout_seconds must be a non-negative integer")
    return value


def validate_stop_policy(value: object) -> str:
    if value is None:
        return DEFAULT_STOP_POLICY
    if not isinstance(value, str) or value not in STOP_POLICIES:
        raise HelperError("stop_policy must be a supported value")
    return value


def default_get_json(url: str, timeout_seconds: float = 2.0) -> dict[str, Any]:
    try:
        response = httpx.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HelperError("HTTP readiness check failed.") from exc
    if not isinstance(payload, dict):
        raise HelperError("HTTP readiness check returned invalid JSON.")
    return payload


@dataclass
class HelperManager:
    project_root: Path
    state_path: Path = DEFAULT_STATE_PATH
    log_dir: Path = DEFAULT_LOG_DIR
    get_json: Callable[[str, float], dict[str, Any]] = default_get_json
    popen: Callable[..., Any] = subprocess.Popen
    which: Callable[[str], str | None] = shutil.which
    sleep: Callable[[float], None] = time.sleep
    ready_timeout_seconds: float = 30.0

    def handle_message(self, message: dict[str, object]) -> dict[str, object]:
        try:
            message_type = message.get("type")
            if message_type == "ping":
                return {"ok": True, "type": "pong"}
            if message_type == "ensure_ready":
                return self.ensure_ready(message)
            raise HelperError("Unsupported helper message type.")
        except HelperError as exc:
            return {"ok": False, "error": str(exc)}

    def ensure_ready(self, message: dict[str, object]) -> dict[str, object]:
        service_url = normalize_service_url(message.get("service_url", DEFAULT_SERVICE_URL))
        idle_timeout_seconds = validate_idle_timeout(message.get("idle_timeout_seconds"))
        stop_policy = validate_stop_policy(message.get("stop_ollama_policy"))
        startup_processes: list[Any] = []
        try:
            ollama_started, ollama_process = self.ensure_ollama()
            if ollama_process is not None:
                startup_processes.append(ollama_process)
            translate_started, translate_process = self.ensure_translate_service(
                service_url=service_url,
                idle_timeout_seconds=idle_timeout_seconds,
                stop_policy=stop_policy,
                ollama_started_by_helper=ollama_started,
            )
            if translate_process is not None:
                startup_processes.append(translate_process)
            self.wait_for_health(service_url)
        except HelperError:
            for process in reversed(startup_processes):
                self.terminate_process(process)
            raise
        return {
            "ok": True,
            "type": "ready",
            "service_url": service_url,
            "ollama_started": ollama_started,
            "translate_started": translate_started,
        }

    def ensure_ollama(self) -> tuple[bool, Any | None]:
        try:
            self.get_json(OLLAMA_TAGS_URL, 2.0)
            return False, None
        except HelperError:
            pass

        ollama_bin = self.which("ollama")
        if ollama_bin is None:
            raise HelperError("Ollama is not installed or not available on PATH.")

        log_path = self.log_dir / "ollama.log"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab") as log_file:
                process = self.popen(
                    [ollama_bin, "serve"],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except OSError as exc:
            raise HelperError("Could not start Ollama.") from exc
        try:
            self.write_state(
                {
                    "ollama_pid": getattr(process, "pid", None),
                    "ollama_started_by_helper": True,
                }
            )
        except HelperError:
            self.terminate_process(process)
            raise
        return True, process

    def ensure_translate_service(
        self,
        *,
        service_url: str,
        idle_timeout_seconds: int,
        stop_policy: str,
        ollama_started_by_helper: bool,
    ) -> tuple[bool, Any | None]:
        health_url = f"{service_url}/health"
        try:
            self.get_json(health_url, 2.0)
            return False, None
        except HelperError:
            pass

        parsed = urlparse(service_url)
        if parsed.hostname is None or parsed.port is None:
            raise HelperError("Service URL is invalid.")

        translate_bin = self.project_root / ".venv" / "bin" / "translate"
        args = [
            str(translate_bin),
            "serve",
            "--host",
            parsed.hostname,
            "--port",
            str(parsed.port),
            "--idle-timeout-seconds",
            str(idle_timeout_seconds),
            "--stop-ollama-policy",
            stop_policy,
        ]

        log_path = self.log_dir / "translate-service.log"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab") as log_file:
                process = self.popen(
                    args,
                    cwd=self.project_root,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except OSError as exc:
            raise HelperError("Could not start translate service.") from exc
        try:
            self.write_state(
                {
                    "translate_pid": getattr(process, "pid", None),
                    "ollama_started_by_helper": ollama_started_by_helper,
                    "service_url": service_url,
                    "started_at": datetime.now(UTC).isoformat(),
                }
            )
        except HelperError:
            self.terminate_process(process)
            raise
        return True, process

    def terminate_process(self, process: Any) -> None:
        try:
            process.terminate()
        except OSError:
            pass

    def wait_for_health(self, service_url: str) -> None:
        health_url = f"{service_url}/health"
        deadline = time.monotonic() + self.ready_timeout_seconds
        while True:
            try:
                self.get_json(health_url, 2.0)
                return
            except HelperError as exc:
                if time.monotonic() >= deadline:
                    raise HelperError("Translate service did not become ready.") from exc
                self.sleep(1.0)

    def write_state(self, updates: dict[str, object | None]) -> None:
        state: dict[str, object] = {}
        try:
            existing = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            existing = None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HelperError(STATE_ERROR) from exc
        if isinstance(existing, dict):
            state.update(existing)

        state.update({key: value for key, value in updates.items() if value is not None})
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise HelperError(STATE_ERROR) from exc


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(input_stream: BinaryIO | None = None, output_stream: BinaryIO | None = None) -> None:
    if input_stream is None:
        input_stream = sys.stdin.buffer
    if output_stream is None:
        output_stream = sys.stdout.buffer

    manager = HelperManager(project_root=default_project_root())
    try:
        message = read_message(input_stream)
    except HelperError as exc:
        response = {"ok": False, "error": str(exc)}
    else:
        response = manager.handle_message(message)
    write_message(output_stream, response)
