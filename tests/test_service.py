import pytest

from translate_service.config import Settings
from translate_service.errors import EmptyTextError, UnsupportedLanguageError
from translate_service.service import TranslationService


class FakeOllamaClient:
    def __init__(self, result: str = "  你好  "):
        self.result = result
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.result

    async def health(self) -> dict[str, object]:
        return {"ok": True, "status": "ok", "model": "translategemma:latest"}


@pytest.mark.asyncio
async def test_translate_uses_defaults_and_returns_normalized_result():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    result = await service.translate(text="Hello")

    assert result == {
        "translation": "你好",
        "source_lang": {"code": "en", "name": "English"},
        "target_lang": {"code": "zh", "name": "Chinese"},
        "model": "translategemma:latest",
    }
    assert client.prompts[0].endswith(":\n\n\nHello")


@pytest.mark.asyncio
async def test_translate_accepts_explicit_languages():
    service = TranslationService(Settings(), FakeOllamaClient("こんにちは"))

    result = await service.translate(text="Hello", source_lang="en", target_lang="ja")

    assert result["target_lang"] == {"code": "ja", "name": "Japanese"}
    assert result["translation"] == "こんにちは"


@pytest.mark.asyncio
async def test_translate_rejects_empty_text_before_ollama_call():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    with pytest.raises(EmptyTextError):
        await service.translate(text="   ")

    assert client.prompts == []


@pytest.mark.asyncio
async def test_translate_rejects_unsupported_language_before_ollama_call():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    with pytest.raises(UnsupportedLanguageError):
        await service.translate(text="Hello", source_lang="EN", target_lang="zh")

    assert client.prompts == []


@pytest.mark.asyncio
async def test_translate_rejects_empty_source_language_before_ollama_call():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    with pytest.raises(UnsupportedLanguageError):
        await service.translate(text="Hello", source_lang="", target_lang="zh")

    assert client.prompts == []


@pytest.mark.asyncio
async def test_translate_rejects_empty_target_language_before_ollama_call():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    with pytest.raises(UnsupportedLanguageError):
        await service.translate(text="Hello", source_lang="en", target_lang="")

    assert client.prompts == []


@pytest.mark.asyncio
async def test_health_returns_normalized_shape():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    result = await service.health()

    assert result == {
        "status": "ok",
        "model": "translategemma:latest",
        "ollama": {"ok": True, "status": "ok", "model": "translategemma:latest"},
    }
