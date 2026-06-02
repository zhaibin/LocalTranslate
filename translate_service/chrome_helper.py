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

    parsed = urlparse(value)
    if parsed.scheme != "http":
        raise HelperError("service_url must use http")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise HelperError("service_url must point to localhost")
    if parsed.username or parsed.password:
        raise HelperError("service_url must not include credentials")

    try:
        port = parsed.port
    except ValueError as exc:
        raise HelperError(f"service_url has an invalid port: {exc}") from exc
    if port is None:
        raise HelperError("service_url must include a port")
    if parsed.path not in {"", "/"}:
        raise HelperError("service_url must not include a path")
    if parsed.params or parsed.query or parsed.fragment:
        raise HelperError("service_url must not include params, query, or fragment")

    return f"http://{parsed.hostname}:{port}"


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
            raise HelperError(f"Unsupported helper message: {message_type!r}")
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
