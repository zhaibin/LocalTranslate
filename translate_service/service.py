from typing import Protocol

from translate_service.config import Settings
from translate_service.errors import EmptyTextError
from translate_service.languages import get_language
from translate_service.prompt import build_prompt


class OllamaLike(Protocol):
    async def generate(self, prompt: str) -> str: ...

    async def health(self) -> dict[str, object]: ...


class TranslationService:
    def __init__(self, settings: Settings, ollama_client: OllamaLike):
        self.settings = settings
        self.ollama_client = ollama_client

    async def translate(
        self,
        *,
        text: str,
        source_lang: str | None = None,
        target_lang: str | None = None,
    ) -> dict[str, object]:
        if not text.strip():
            raise EmptyTextError("Text to translate cannot be empty")

        source_code = self.settings.default_source_lang if source_lang is None else source_lang
        target_code = self.settings.default_target_lang if target_lang is None else target_lang
        source = get_language(source_code)
        target = get_language(target_code)
        prompt = build_prompt(
            source_name=source["name"],
            source_code=source["code"],
            target_name=target["name"],
            target_code=target["code"],
            text=text,
        )
        translation = (await self.ollama_client.generate(prompt)).strip()
        return {
            "translation": translation,
            "source_lang": source,
            "target_lang": target,
            "model": self.settings.ollama_model,
        }

    async def health(self) -> dict[str, object]:
        ollama_health = await self.ollama_client.health()
        return {
            "status": "ok" if ollama_health.get("ok") else "degraded",
            "model": self.settings.ollama_model,
            "ollama": ollama_health,
        }
