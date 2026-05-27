import asyncio
import json

import typer

from translate_service.config import Settings
from translate_service.errors import TranslationError
from translate_service.languages import list_languages
from translate_service.ollama_client import OllamaClient
from translate_service.service import TranslationService

app = typer.Typer(no_args_is_help=True)


def _service() -> TranslationService:
    settings = Settings()
    return TranslationService(settings, OllamaClient(settings))


@app.command()
def text(
    value: str = typer.Argument(...),
    source_lang: str | None = typer.Option(None, "--from"),
    target_lang: str | None = typer.Option(None, "--to"),
):
    async def run():
        result = await _service().translate(
            text=value,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        typer.echo(result["translation"])

    try:
        asyncio.run(run())
    except TranslationError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def languages():
    typer.echo(json.dumps({"languages": list_languages()}, ensure_ascii=False, indent=2))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn

    from translate_service.api.app import create_app

    uvicorn.run(create_app(), host=host, port=port)
