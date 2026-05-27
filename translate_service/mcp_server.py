from mcp.server.fastmcp import FastMCP

from translate_service.config import Settings
from translate_service.languages import list_languages as get_supported_languages
from translate_service.ollama_client import OllamaClient
from translate_service.service import TranslationService


def _service() -> TranslationService:
    settings = Settings()
    return TranslationService(settings, OllamaClient(settings))


def create_mcp_server() -> FastMCP:
    mcp = FastMCP("local-ollama-translation-service")

    @mcp.tool()
    async def translate_text(
        text: str,
        source_lang: str | None = None,
        target_lang: str | None = None,
    ) -> dict[str, object]:
        """Translate text with local Ollama and TranslateGemma."""
        return await _service().translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
        )

    @mcp.tool()
    def list_languages() -> dict[str, object]:
        """List supported source and target language codes."""
        return {"languages": get_supported_languages()}

    @mcp.tool()
    async def health() -> dict[str, object]:
        """Check local Ollama and model status."""
        return await _service().health()

    return mcp


if __name__ == "__main__":
    create_mcp_server().run()
