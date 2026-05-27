import httpx
import pytest
import respx

from translate_service.config import Settings
from translate_service.errors import (
    OllamaModelError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)
from translate_service.ollama_client import OllamaClient


@pytest.mark.asyncio
@respx.mock
async def test_generate_posts_to_ollama_generate_api():
    route = respx.post("http://127.0.0.1:11434/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "你好", "done": True})
    )
    client = OllamaClient(Settings())

    result = await client.generate("prompt")

    assert result == "你好"
    assert route.calls[0].request.content == (
        b'{"model":"translategemma:latest","prompt":"prompt","stream":false}'
    )


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_non_200_to_model_error():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        return_value=httpx.Response(404, json={"error": "model not found"})
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaModelError):
        await client.generate("prompt")


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_timeout():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaTimeoutError):
        await client.generate("prompt")


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_connect_error():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        side_effect=httpx.ConnectError("no service")
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaUnavailableError):
        await client.generate("prompt")
