# Local Ollama Translation Service

Local translation service for Ollama and `translategemma:latest`.

## Commands

```bash
translate text --from en --to zh "Hello"
translate languages
translate serve --host 127.0.0.1 --port 8000
```

## HTTP

```bash
curl -X POST http://127.0.0.1:8000/translate \
  -H 'content-type: application/json' \
  -d '{"text":"Hello","source_lang":"en","target_lang":"zh"}'
```

## MCP

Run the MCP stdio server with:

```bash
python -m translate_service.mcp_server
```
