from translate_service.mcp_server import create_mcp_server


def test_mcp_server_can_be_created():
    server = create_mcp_server()

    assert server.name == "local-ollama-translation-service"
