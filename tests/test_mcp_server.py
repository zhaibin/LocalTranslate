import pytest

import translate_service.mcp_server as mcp_server
from translate_service.mcp_server import create_mcp_server


def test_mcp_server_can_be_created():
    server = create_mcp_server()

    assert server.name == "local-ollama-translation-service"


@pytest.mark.asyncio
async def test_mcp_server_registers_expected_tools():
    server = create_mcp_server()

    tools = await server.list_tools()

    assert {tool.name for tool in tools} == {"translate_text", "list_languages", "health"}


@pytest.mark.asyncio
async def test_translate_text_tool_forwards_arguments(monkeypatch):
    calls = []

    class FakeService:
        async def translate(
            self,
            *,
            text: str,
            source_lang: str | None = None,
            target_lang: str | None = None,
        ):
            calls.append(
                {
                    "text": text,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                }
            )
            return {"translation": "你好"}

    monkeypatch.setattr(mcp_server, "_service", lambda: FakeService())
    server = create_mcp_server()

    _content, structured_result = await server.call_tool(
        "translate_text",
        {"text": "Hello", "source_lang": "en", "target_lang": "zh"},
    )

    assert structured_result == {"translation": "你好"}
    assert calls == [{"text": "Hello", "source_lang": "en", "target_lang": "zh"}]
