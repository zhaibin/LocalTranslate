from __future__ import annotations

import io
import json
import struct
import subprocess
import tomllib
from pathlib import Path

import pytest

from translate_service.chrome_helper import (
    MAX_MESSAGE_BYTES,
    HelperError,
    HelperManager,
    main,
    normalize_service_url,
    read_message,
    validate_idle_timeout,
    validate_stop_policy,
    write_message,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


class FakePopen:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.next_pid = 3000

    def __call__(self, args: list[str], **kwargs: object) -> FakeProcess:
        self.next_pid += 1
        process = FakeProcess(self.next_pid)
        self.calls.append({"args": args, "kwargs": kwargs, "process": process})
        return process


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
        "http://127.0.0.1:0",
    ],
)
def test_normalize_service_url_rejects_unsupported_urls(value: str) -> None:
    with pytest.raises(HelperError):
        normalize_service_url(value)


@pytest.mark.parametrize(
    "value",
    [
        "http://127.0.0.1:abc",
        "http://127.0.0.1:99999",
    ],
)
def test_normalize_service_url_rejects_invalid_ports_with_helper_error(value: str) -> None:
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


def test_ensure_ready_starts_local_processes_when_checks_are_unreachable(
    tmp_path: Path,
) -> None:
    checks: list[str] = []
    popen = FakePopen()

    def fake_get_json(url: str, timeout_seconds: float = 2.0) -> dict[str, object]:
        checks.append(url)
        if len(checks) < 3:
            raise HelperError("unreachable")
        return {"status": "ok"}

    manager = HelperManager(
        project_root=ROOT,
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
        get_json=fake_get_json,
        popen=popen,
        which=lambda command: f"/bin/{command}",
        sleep=lambda seconds: None,
    )

    response = manager.ensure_ready(
        {
            "type": "ensure_ready",
            "service_url": "http://127.0.0.1:8000",
            "idle_timeout_seconds": 123,
            "stop_ollama_policy": "always",
        }
    )

    assert response == {
        "ok": True,
        "type": "ready",
        "service_url": "http://127.0.0.1:8000",
        "ollama_started": True,
        "translate_started": True,
    }
    assert checks == [
        "http://127.0.0.1:11434/api/tags",
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/health",
    ]
    assert popen.calls[0]["args"] == ["/bin/ollama", "serve"]
    assert popen.calls[0]["kwargs"]["stdin"] == subprocess.DEVNULL
    assert popen.calls[1]["args"] == [
        str(ROOT / ".venv" / "bin" / "translate"),
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--idle-timeout-seconds",
        "123",
        "--stop-ollama-policy",
        "always",
    ]
    assert popen.calls[1]["kwargs"]["stdin"] == subprocess.DEVNULL


def test_ensure_ready_returns_ready_without_starting_when_services_are_reachable(
    tmp_path: Path,
) -> None:
    checks: list[str] = []
    popen = FakePopen()

    def fake_get_json(url: str, timeout_seconds: float = 2.0) -> dict[str, object]:
        checks.append(url)
        return {"ok": True}

    manager = HelperManager(
        project_root=ROOT,
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
        get_json=fake_get_json,
        popen=popen,
        which=lambda command: f"/bin/{command}",
        sleep=lambda seconds: None,
    )

    response = manager.ensure_ready(
        {"type": "ensure_ready", "service_url": "http://localhost:8123/"}
    )

    assert response == {
        "ok": True,
        "type": "ready",
        "service_url": "http://localhost:8123",
        "ollama_started": False,
        "translate_started": False,
    }
    assert checks == [
        "http://127.0.0.1:11434/api/tags",
        "http://localhost:8123/health",
        "http://localhost:8123/health",
    ]
    assert popen.calls == []


def test_helper_writes_state_file_when_it_starts_processes(tmp_path: Path) -> None:
    popen = FakePopen()
    calls = 0

    def fake_get_json(url: str, timeout_seconds: float = 2.0) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise HelperError("unreachable")
        return {"status": "ok"}

    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"preserved": True}), encoding="utf-8")
    manager = HelperManager(
        project_root=ROOT,
        state_path=state_path,
        log_dir=tmp_path,
        get_json=fake_get_json,
        popen=popen,
        which=lambda command: f"/bin/{command}",
        sleep=lambda seconds: None,
    )

    manager.ensure_ready({"type": "ensure_ready", "service_url": "http://127.0.0.1:8000"})

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["preserved"] is True
    assert state["ollama_pid"] == 3001
    assert state["translate_pid"] == 3002
    assert state["ollama_started_by_helper"] is True
    assert state["service_url"] == "http://127.0.0.1:8000"
    assert "started_at" in state


def test_write_state_rejects_corrupt_utf8_state_with_bounded_error(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_bytes(b"\xff")
    manager = HelperManager(project_root=ROOT, state_path=state_path, log_dir=tmp_path)

    with pytest.raises(HelperError, match="^Could not write helper state\\.$"):
        manager.write_state({"ollama_pid": 123})


def test_write_state_wraps_write_failure_with_bounded_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = HelperManager(
        project_root=ROOT,
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
    )

    def fail_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        raise OSError("raw path and system details")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    with pytest.raises(HelperError, match="^Could not write helper state\\.$"):
        manager.write_state({"ollama_pid": 123})


def test_ensure_ollama_terminates_started_process_when_state_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    popen = FakePopen()

    def fail_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        raise OSError("raw path and system details")

    monkeypatch.setattr(Path, "write_text", fail_write_text)
    manager = HelperManager(
        project_root=ROOT,
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
        get_json=lambda url, timeout_seconds=2.0: (_ for _ in ()).throw(
            HelperError("unreachable")
        ),
        popen=popen,
        which=lambda command: f"/bin/{command}",
    )

    response = manager.handle_message(
        {"type": "ensure_ready", "service_url": "http://127.0.0.1:8000"}
    )

    assert response == {"ok": False, "error": "Could not write helper state."}
    assert len(popen.calls) == 1
    assert popen.calls[0]["process"].terminated is True


def test_ensure_ready_terminates_ollama_when_later_translate_state_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    popen = FakePopen()
    original_write_text = Path.write_text
    write_count = 0

    def fail_second_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("raw path and system details")
        return original_write_text(
            self,
            data,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    monkeypatch.setattr(Path, "write_text", fail_second_write_text)
    manager = HelperManager(
        project_root=ROOT,
        state_path=tmp_path / "state.json",
        log_dir=tmp_path,
        get_json=lambda url, timeout_seconds=2.0: (_ for _ in ()).throw(
            HelperError("unreachable")
        ),
        popen=popen,
        which=lambda command: f"/bin/{command}",
    )

    response = manager.handle_message(
        {"type": "ensure_ready", "service_url": "http://127.0.0.1:8000"}
    )

    assert response == {"ok": False, "error": "Could not write helper state."}
    assert len(popen.calls) == 2
    assert popen.calls[0]["process"].terminated is True
    assert popen.calls[1]["process"].terminated is True


def test_validate_idle_timeout_uses_default_and_accepts_non_negative_integer() -> None:
    assert validate_idle_timeout(None) == 900
    assert validate_idle_timeout(0) == 0
    assert validate_idle_timeout(15) == 15


@pytest.mark.parametrize("value", [-1, "10", 1.5, True])
def test_validate_idle_timeout_rejects_negative_or_non_integer(value: object) -> None:
    with pytest.raises(HelperError):
        validate_idle_timeout(value)


@pytest.mark.parametrize(
    "value",
    ["never", "if-started-by-helper", "always"],
)
def test_validate_stop_policy_accepts_supported_values(value: str) -> None:
    assert validate_stop_policy(value) == value


def test_validate_stop_policy_uses_default() -> None:
    assert validate_stop_policy(None) == "if-started-by-helper"


@pytest.mark.parametrize("value", ["", "sometimes", 123, True])
def test_validate_stop_policy_rejects_invalid_values(value: object) -> None:
    with pytest.raises(HelperError):
        validate_stop_policy(value)


def test_main_returns_framed_error_for_malformed_native_input() -> None:
    input_stream = io.BytesIO(struct.pack("<I", 1) + b"{")
    output_stream = io.BytesIO()

    main(input_stream=input_stream, output_stream=output_stream)

    output_stream.seek(0)
    response = read_message(output_stream)
    assert response["ok"] is False
    assert "Invalid native messaging JSON" in str(response["error"])


def test_main_returns_bounded_framed_error_for_long_unsupported_type() -> None:
    input_stream = io.BytesIO()
    output_stream = io.BytesIO()
    write_message(input_stream, {"type": "x" * (MAX_MESSAGE_BYTES - 20)})
    input_stream.seek(0)

    main(input_stream=input_stream, output_stream=output_stream)

    raw_response = output_stream.getvalue()
    body_length = struct.unpack("<I", raw_response[:4])[0]
    assert body_length <= MAX_MESSAGE_BYTES

    output_stream.seek(0)
    response = read_message(output_stream)
    assert response["ok"] is False
    assert "Unsupported helper message" in str(response["error"])


def test_main_returns_bounded_framed_error_for_long_invalid_service_url_port() -> None:
    input_stream = io.BytesIO()
    output_stream = io.BytesIO()
    write_message(
        input_stream,
        {"type": "ensure_ready", "service_url": f"http://127.0.0.1:{'9' * 65400}"},
    )
    input_stream.seek(0)

    main(input_stream=input_stream, output_stream=output_stream)

    raw_response = output_stream.getvalue()
    body_length = struct.unpack("<I", raw_response[:4])[0]
    assert body_length <= MAX_MESSAGE_BYTES

    output_stream.seek(0)
    response = read_message(output_stream)
    assert response["ok"] is False
    assert response["error"] == "Service URL must include a valid port."


def test_main_returns_framed_error_for_malformed_bracketed_service_url() -> None:
    input_stream = io.BytesIO()
    output_stream = io.BytesIO()
    write_message(
        input_stream,
        {"type": "ensure_ready", "service_url": "http://[::1:8000"},
    )
    input_stream.seek(0)

    main(input_stream=input_stream, output_stream=output_stream)

    output_stream.seek(0)
    response = read_message(output_stream)
    assert response["ok"] is False
    assert response["error"] == "Service URL is invalid."


def test_pyproject_declares_chrome_helper_console_script() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert pyproject["project"]["scripts"]["local-translate-chrome-helper"] == (
        "translate_service.chrome_helper:main"
    )
