import mimetypes
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
mimetypes.add_type("application/javascript", ".js")


def create_app(service: TranslationService | None = None) -> FastAPI:
    app = FastAPI(title="Local Ollama Translation Service")
    if service is None:
        settings = Settings()
        service = TranslationService(settings, OllamaClient(settings))
    app.state.translation_service = service
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
