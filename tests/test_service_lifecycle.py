import json
import time

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from translate_service.api.app import StopOllamaPolicy, create_app
from translate_service.cli import app as cli_app

runner = CliRunner()


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
    app.state.last_activity_at = time.monotonic() - 100

    assert app.state.idle_timeout_seconds == 0
    assert app.state.stop_ollama_policy == StopOllamaPolicy.NEVER
    assert app.state.should_stop_for_idle_timeout() is False


def test_should_stop_for_idle_timeout():
    app = create_app(FakeService(), idle_timeout_seconds=1)
    app.state.last_activity_at = time.monotonic() - 2

    assert app.state.should_stop_for_idle_timeout() is True


def test_never_stop_policy_does_not_touch_helper_state(tmp_path):
    state_path = tmp_path / "helper-state.json"
    state_path.write_text(
        json.dumps({"ollama_started_by_helper": True, "ollama_pid": 12345}),
        encoding="utf-8",
    )
    stopped: list[int] = []
    app = create_app(
        FakeService(),
        stop_ollama_policy=StopOllamaPolicy.NEVER,
        helper_state_path=state_path,
        stop_pid=stopped.append,
    )

    app.state.stop_ollama_if_needed()

    assert stopped == []
    assert state_path.exists()


def test_stop_ollama_if_started_by_helper_stops_recorded_pid(tmp_path):
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


def test_always_stop_policy_stops_integer_pid(tmp_path):
    state_path = tmp_path / "helper-state.json"
    state_path.write_text(json.dumps({"ollama_pid": 12345}), encoding="utf-8")
    stopped: list[int] = []
    app = create_app(
        FakeService(),
        stop_ollama_policy=StopOllamaPolicy.ALWAYS,
        helper_state_path=state_path,
        stop_pid=stopped.append,
    )

    app.state.stop_ollama_if_needed()

    assert stopped == [12345]
    assert not state_path.exists()


def test_stop_policy_treats_invalid_json_as_empty_state(tmp_path):
    state_path = tmp_path / "helper-state.json"
    state_path.write_text("{", encoding="utf-8")
    stopped: list[int] = []
    app = create_app(
        FakeService(),
        stop_ollama_policy=StopOllamaPolicy.ALWAYS,
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

    result = runner.invoke(cli_app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--idle-timeout-seconds" in result.stdout
    assert "--stop-ollama-policy" in result.stdout
