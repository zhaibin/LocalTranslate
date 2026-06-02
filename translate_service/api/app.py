import asyncio
import json
import mimetypes
import os
import signal
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from translate_service.config import Settings
from translate_service.errors import (
    EmptyTextError,
    OllamaModelError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    UnsupportedLanguageError,
)
from translate_service.ollama_client import OllamaClient
from translate_service.service import TranslationService


WEB_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"
WEB_INDEX_PATH = WEB_STATIC_DIR / "index.html"
HELPER_STATE_PATH = (
    Path.home() / "Library" / "Application Support" / "LocalTranslate" / "helper-state.json"
)
mimetypes.add_type("application/javascript", ".js")


class StopOllamaPolicy(StrEnum):
    NEVER = "never"
    IF_STARTED_BY_HELPER = "if-started-by-helper"
    ALWAYS = "always"


def stop_pid_with_sigterm(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)


def create_app(
    service: TranslationService | None = None,
    *,
    idle_timeout_seconds: int = 0,
    stop_ollama_policy: StopOllamaPolicy = StopOllamaPolicy.NEVER,
    helper_state_path: Path = HELPER_STATE_PATH,
    stop_pid: Callable[[int], None] = stop_pid_with_sigterm,
    on_idle_timeout: Callable[[], None] | None = None,
) -> FastAPI:
    app = FastAPI(title="Local Ollama Translation Service")
    if service is None:
        settings = Settings()
        service = TranslationService(settings, OllamaClient(settings))
    app.state.translation_service = service
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
        if policy == StopOllamaPolicy.NEVER:
            return

        state_path = app.state.helper_state_path
        state: dict[str, object] = {}
        if state_path.exists():
            try:
                loaded_state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded_state = {}
            if isinstance(loaded_state, dict):
                state = loaded_state

        pid = state.get("ollama_pid")
        started_by_helper = state.get("ollama_started_by_helper") is True
        has_integer_pid = type(pid) is int
        should_stop = policy == StopOllamaPolicy.ALWAYS or (
            policy == StopOllamaPolicy.IF_STARTED_BY_HELPER
            and started_by_helper
            and has_integer_pid
        )
        if should_stop and has_integer_pid:
            app.state.stop_pid(pid)

        try:
            state_path.unlink(missing_ok=True)
        except OSError:
            pass

    app.state.should_stop_for_idle_timeout = should_stop_for_idle_timeout
    app.state.stop_ollama_if_needed = stop_ollama_if_needed

    @app.middleware("http")
    async def track_activity(request: Request, call_next):
        app.state.last_activity_at = time.monotonic()
        return await call_next(request)

    async def idle_monitor():
        while True:
            await asyncio.sleep(1)
            if app.state.should_stop_for_idle_timeout():
                app.state.stop_ollama_if_needed()
                on_idle_timeout()
                return

    if idle_timeout_seconds > 0 and on_idle_timeout is not None:

        @app.on_event("startup")
        async def start_idle_monitor():
            app.state.idle_monitor_task = asyncio.create_task(idle_monitor())

    app.mount("/static", StaticFiles(directory=WEB_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def web_index():
        return FileResponse(WEB_INDEX_PATH)

    from translate_service.api.routes_system import router as system_router
    from translate_service.api.routes_translate import router as translate_router

    app.include_router(translate_router)
    app.include_router(system_router)
    register_exception_handlers(app)
    return app


def get_service(request: Request) -> TranslationService:
    return request.app.state.translation_service


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EmptyTextError)
    async def empty_text_handler(_request: Request, exc: EmptyTextError):
        return JSONResponse(status_code=400, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(UnsupportedLanguageError)
    async def unsupported_language_handler(_request: Request, exc: UnsupportedLanguageError):
        return JSONResponse(status_code=400, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(OllamaUnavailableError)
    async def unavailable_handler(_request: Request, exc: OllamaUnavailableError):
        return JSONResponse(status_code=503, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(OllamaModelError)
    async def model_handler(_request: Request, exc: OllamaModelError):
        return JSONResponse(status_code=502, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(OllamaTimeoutError)
    async def timeout_handler(_request: Request, exc: OllamaTimeoutError):
        return JSONResponse(status_code=504, content={"error": exc.error_code, "message": str(exc)})
