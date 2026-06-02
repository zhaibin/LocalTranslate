from __future__ import annotations

import io
import json
import struct
import tomllib
from pathlib import Path

import pytest

from translate_service.chrome_helper import (
    MAX_MESSAGE_BYTES,
    HelperError,
    HelperManager,
    normalize_service_url,
    read_message,
    write_message,
)

ROOT = Path(__file__).resolve().parents[1]


def test_native_messaging_frame_read_write_uses_little_endian_length() -> None:
    stream = io.BytesIO()

    write_message(stream, {"ok": True, "type": "pong"})

    raw = stream.getvalue()
    assert struct.unpack("<I", raw[:4]) == (len(raw) - 4,)
    assert json.loads(raw[4:].decode("utf-8")) == {"ok": True, "type": "pong"}

    stream.seek(0)
    assert read_message(stream) == {"ok": True, "type": "pong"}


def test_read_message_rejects_oversized_frame() -> None:
    stream = io.BytesIO(struct.pack("<I", MAX_MESSAGE_BYTES + 1))

    with pytest.raises(HelperError, match="too large"):
        read_message(stream)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
        ("http://localhost:8000", "http://localhost:8000"),
    ],
)
def test_normalize_service_url_accepts_local_http_urls(value: str, expected: str) -> None:
    assert normalize_service_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://127.0.0.1:8000",
        "http://192.168.1.5:8000",
        "http://user:pass@127.0.0.1:8000",
        "http://127.0.0.1:8000/api",
        "http://127.0.0.1",
    ],
)
def test_normalize_service_url_rejects_unsupported_urls(value: str) -> None:
    with pytest.raises(HelperError):
        normalize_service_url(value)


def test_helper_manager_ping_returns_pong(tmp_path: Path) -> None:
    manager = HelperManager(project_root=ROOT, state_path=tmp_path / "state.json", log_dir=tmp_path)

    assert manager.handle_message({"type": "ping"}) == {"ok": True, "type": "pong"}


def test_helper_manager_unknown_message_returns_error(tmp_path: Path) -> None:
    manager = HelperManager(project_root=ROOT, state_path=tmp_path / "state.json", log_dir=tmp_path)

    response = manager.handle_message({"type": "unknown"})

    assert response["ok"] is False
    assert "Unsupported helper message" in str(response["error"])


def test_pyproject_declares_chrome_helper_console_script() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert pyproject["project"]["scripts"]["local-translate-chrome-helper"] == (
        "translate_service.chrome_helper:main"
    )
