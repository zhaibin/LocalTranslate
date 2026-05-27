import json

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
    assert json.loads(route.calls[0].request.content) == {
        "model": "translategemma:latest",
        "prompt": "prompt",
        "stream": False,
    }


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


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_http_error():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        side_effect=httpx.HTTPError("broken")
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaUnavailableError):
        await client.generate("prompt")


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_invalid_json_to_model_error():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        return_value=httpx.Response(200, content=b"not json")
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaModelError):
        await client.generate("prompt")


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_non_object_response_to_model_error():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        return_value=httpx.Response(200, json=["not", "an", "object"])
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaModelError):
        await client.generate("prompt")


@pytest.mark.asyncio
@respx.mock
async def test_health_returns_ok_when_model_available():
    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "translategemma:latest"}]},
        )
    )
    client = OllamaClient(Settings())

    result = await client.health()

    assert result == {
        "ok": True,
        "status": "ok",
        "model": "translategemma:latest",
        "model_available": True,
    }


@pytest.mark.asyncio
@respx.mock
async def test_health_returns_degraded_when_model_missing():
    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "other-model:latest"}]},
        )
    )
    client = OllamaClient(Settings())

    result = await client.health()

    assert result == {
        "ok": False,
        "status": "degraded",
        "model": "translategemma:latest",
        "model_available": False,
    }


@pytest.mark.asyncio
@respx.mock
async def test_health_returns_degraded_for_invalid_json():
    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(200, content=b"not json")
    )
    client = OllamaClient(Settings())

    result = await client.health()

    assert result == {
        "ok": False,
        "status": "degraded",
        "reason": "invalid_response",
        "model": "translategemma:latest",
    }


@pytest.mark.asyncio
@respx.mock
async def test_health_returns_degraded_for_non_object_response():
    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(200, json=["not", "an", "object"])
    )
    client = OllamaClient(Settings())

    result = await client.health()

    assert result == {
        "ok": False,
        "status": "degraded",
        "reason": "invalid_response",
        "model": "translategemma:latest",
    }
