# Local Ollama Translation Service

Local translation service for Ollama and `translategemma:latest`.

## Requirements

- Python 3.11+
- A running Ollama server
- The `translategemma:latest` model installed locally:

```bash
ollama pull translategemma:latest
```

## Configuration

Copy `.env.example` to `.env` and adjust values if your Ollama host, model, or default
languages differ.

```bash
cp .env.example .env
```

Defaults use English (`en`) as the source language and Chinese (`zh`) as the target
language. Pass explicit language codes per request to override them.

## CLI

```bash
translate text --from en --to zh "Hello"
translate languages
translate serve --host 127.0.0.1 --port 8000
```

## HTTP

Start the API server:

```bash
translate serve --host 127.0.0.1 --port 8000
```

Translate text:

```bash
curl -X POST http://127.0.0.1:8000/translate \
  -H 'content-type: application/json' \
  -d '{"text":"Hello","source_lang":"en","target_lang":"zh"}'
```

List languages and check service health:

```bash
curl http://127.0.0.1:8000/languages
curl http://127.0.0.1:8000/health
```

## MCP

Run the MCP stdio server with:

```bash
python -m translate_service.mcp_server
```

Available MCP tools:

- `translate_text`: translate text with optional source and target language codes.
- `list_languages`: return supported language codes.
- `health`: check the configured Ollama model status.

## Development Checks

```bash
pytest -q
ruff check .
python -c 'from translate_service.prompt import build_prompt; p=build_prompt(source_name="English",source_code="en",target_name="Chinese",target_code="zh",text="Hello"); print(repr(p[-12:]))'
```
