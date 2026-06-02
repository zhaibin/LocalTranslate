import json
import time
from threading import Event, Thread

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


class SlowService(FakeService):
    async def translate(self, *, text: str, source_lang=None, target_lang=None):
        request_started.set()
        allow_request_to_finish.wait(timeout=2)
        return await super().translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
        )


request_started = Event()
allow_request_to_finish = Event()


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


def test_idle_timeout_does_not_fire_while_request_is_active():
    fired: list[None] = []
    request_started.clear()
    allow_request_to_finish.clear()
    app = create_app(
        SlowService(),
        idle_timeout_seconds=1,
        on_idle_timeout=lambda: fired.append(None),
    )
    client = TestClient(app)
    responses = []

    def post_translate() -> None:
        responses.append(
            client.post(
                "/translate",
                json={"text": "hello", "source_lang": "en", "target_lang": "zh"},
            )
        )

    with client:
        request_thread = Thread(target=post_translate)
        request_thread.start()
        try:
            assert request_started.wait(timeout=2)
            app.state.last_activity_at = time.monotonic() - 2

            assert app.state.should_stop_for_idle_timeout() is False
            assert fired == []

            allow_request_to_finish.set()
            request_thread.join(timeout=2)
        finally:
            allow_request_to_finish.set()
            request_thread.join(timeout=2)

        assert not request_thread.is_alive()
        assert responses[0].status_code == 200
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


def test_idle_shutdown_callback_runs_when_stale_pid_stop_fails(tmp_path):
    state_path = tmp_path / "helper-state.json"
    state_path.write_text(json.dumps({"ollama_pid": 12345}), encoding="utf-8")
    fired: list[None] = []

    def stop_pid(_pid: int) -> None:
        raise ProcessLookupError

    def on_idle_timeout() -> None:
        fired.append(None)

    app = create_app(
        FakeService(),
        idle_timeout_seconds=1,
        stop_ollama_policy=StopOllamaPolicy.ALWAYS,
        helper_state_path=state_path,
        stop_pid=stop_pid,
        on_idle_timeout=on_idle_timeout,
    )
    app.state.last_activity_at = time.monotonic() - 2

    if app.state.should_stop_for_idle_timeout():
        app.state.stop_ollama_if_needed()
        on_idle_timeout()

    assert fired == [None]
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
