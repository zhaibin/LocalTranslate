import asyncio
import json
import sys
from typing import Annotated

import typer

from translate_service.config import Settings
from translate_service.errors import TranslationError
from translate_service.languages import list_languages
from translate_service.ollama_client import OllamaClient
from translate_service.service import TranslationService

app = typer.Typer(no_args_is_help=True)


def _encode_for_stdout(value: str, encoding: str | None) -> str:
    if not encoding:
        return value
    return value.encode(encoding, errors="backslashreplace").decode(encoding)


def _echo(value: str) -> None:
    typer.echo(_encode_for_stdout(value, sys.stdout.encoding))


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
        _echo(result["translation"])

    try:
        asyncio.run(run())
    except TranslationError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def languages():
    _echo(json.dumps({"languages": list_languages()}, ensure_ascii=False, indent=2))


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    idle_timeout_seconds: Annotated[int, typer.Option("--idle-timeout-seconds")] = 0,
    stop_ollama_policy: Annotated[str, typer.Option("--stop-ollama-policy")] = "never",
):
    import uvicorn

    from translate_service.api.app import StopOllamaPolicy, create_app

    try:
        policy = StopOllamaPolicy(stop_ollama_policy)
    except ValueError as exc:
        valid_values = ", ".join(policy.value for policy in StopOllamaPolicy)
        raise typer.BadParameter(
            f"Invalid stop Ollama policy '{stop_ollama_policy}'. Expected one of: {valid_values}."
        ) from exc

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
