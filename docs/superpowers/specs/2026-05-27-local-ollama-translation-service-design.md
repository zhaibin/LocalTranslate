# Local Ollama Translation Service Design

Date: 2026-05-27

## Goal

Build a local translation service around Ollama and the `translategemma:latest` model. The service must expose one shared translation core through three local entry points:

- HTTP API for scripts, applications, and browser-based debugging.
- CLI for terminal usage and service startup.
- MCP stdio server for local agent tools.

All entry points must share the same language validation, prompt generation, Ollama call behavior, error handling, and result shape.

## Non-Goals

The first version will not include:

- OpenAI-compatible `/v1/chat/completions` endpoints.
- Automatic language detection.
- Glossaries, style controls, domain controls, or Markdown-preservation modes.
- Translation history, caching, background queues, or a Web UI.
- Remote MCP transport.

## Architecture

The project will be a Python package named `translate_service`. The core API is `TranslationService.translate()`. HTTP routes, CLI commands, and MCP tools act as thin adapters that parse inputs and call this core service.

Proposed module layout:

```text
translate_service/
  config.py
  languages.py
  prompt.py
  ollama_client.py
  service.py
  api/
    routes_translate.py
    routes_system.py
  cli.py
  mcp_server.py
```

Module responsibilities:

- `config.py`: Reads environment variables and `.env` values.
- `languages.py`: Stores the supported language table, validates language codes, and resolves display names.
- `prompt.py`: Builds the exact TranslateGemma prompt.
- `ollama_client.py`: Calls local Ollama and maps transport/model failures into service-level errors.
- `service.py`: Validates input, resolves languages, builds prompts, calls Ollama, cleans output, and returns a normalized translation result.
- `api/`: Exposes HTTP endpoints using the shared service.
- `cli.py`: Exposes terminal commands using the shared service.
- `mcp_server.py`: Exposes MCP tools using the shared service.

## Configuration

Default configuration:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=translategemma:latest
DEFAULT_SOURCE_LANG=en
DEFAULT_TARGET_LANG=zh
REQUEST_TIMEOUT_SECONDS=120
```

The implementation should load these from environment variables and optionally from `.env`.

## Supported Languages

The service will include the provided supported language table as internal data. Language matching is exact by code, preserving region and script variants such as `en-GB`, `zh-Hans`, and `zh-Hant-HK`.

The language module exposes:

- Validation for source and target language codes.
- Lookup from language code to display language name.
- A list endpoint/tool-friendly structure containing all supported codes and names.

## Prompt Format

The prompt builder must produce exactly one user prompt using the TranslateGemma structure:

```text
You are a professional {SOURCE_LANG} ({SOURCE_CODE}) to {TARGET_LANG} ({TARGET_CODE}) translator. Your goal is to accurately convey the meaning and nuances of the original {SOURCE_LANG} text while adhering to {TARGET_LANG} grammar, vocabulary, and cultural sensitivities.
Produce only the {TARGET_LANG} translation, without any additional explanations or commentary. Please translate the following {SOURCE_LANG} text into {TARGET_LANG}:



{TEXT}
```

There must be two blank lines before the text to translate. In the rendered prompt string, this means the final colon line is followed by three newline characters before `{TEXT}`: `:\n\n\n{TEXT}`.

The first version will not add extra prompt controls. It will trim leading and trailing whitespace from the model response but will not attempt complex parsing if the model returns commentary.

## HTTP API

### `POST /translate`

Request:

```json
{
  "text": "Hello",
  "source_lang": "en",
  "target_lang": "zh"
}
```

`source_lang` and `target_lang` may be omitted, in which case the configured defaults are used.

Response:

```json
{
  "translation": "你好",
  "source_lang": {"code": "en", "name": "English"},
  "target_lang": {"code": "zh", "name": "Chinese"},
  "model": "translategemma:latest"
}
```

### `GET /languages`

Returns all supported language codes and names.

### `GET /health`

Returns service status, configured model, Ollama reachability, and a status value such as `ok` or `degraded`.

## CLI

The CLI will expose:

```bash
translate text --from en --to zh "Hello"
translate languages
translate serve --host 127.0.0.1 --port 8000
```

CLI commands must call the same core service and present clear parameter errors for empty text or unsupported language codes.

## MCP Server

The MCP server will use stdio transport in the first version. It will expose:

- `translate_text(text, source_lang, target_lang)`: Returns the same normalized structure as `POST /translate`.
- `list_languages()`: Returns all supported language codes and names.
- `health()`: Returns local service, Ollama, and model status.

MCP tools must call the same core service as HTTP and CLI.

## Data Flow

```text
Entry point parses request
-> TranslationService validates text and language codes
-> languages resolves display names
-> prompt builds the TranslateGemma prompt
-> ollama_client calls Ollama with model translategemma:latest
-> service trims the model response
-> entry point returns normalized result
```

The Ollama client should prefer the local generate-style API because TranslateGemma receives one complete prompt. This detail remains internal to `ollama_client.py` so it can change later without affecting HTTP, CLI, or MCP contracts.

## Error Handling

HTTP error mapping:

- Unsupported language code: `400`.
- Empty text: `400`.
- Ollama service unavailable: `503`.
- Ollama model or generation error: `502`.
- Request timeout: `504`.
- Unexpected server error: `500`.

CLI and MCP should map the same service errors into their native error formats.

Responses and logs should include safe diagnostic details such as language direction, text length, elapsed time, model name, and error type. They should not log source text or translated text by default.

## Testing

Required tests:

- `languages` unit tests for valid codes, invalid codes, and common variants such as `zh-Hans` and `zh-Hant-HK`.
- `prompt` unit tests for exact template rendering and the required two-blank-line separation before text.
- `service` unit tests using a mocked Ollama client for success, invalid language, empty text, timeout, unavailable Ollama, and model error.
- HTTP tests for `/translate`, `/languages`, and `/health`.
- CLI tests for command parsing, success output, and parameter errors.
- MCP tests for tool registration and tool calls using the same core service.

Optional local integration tests may call real Ollama only when Ollama is reachable and `translategemma:latest` is available. These tests should not be part of the default required test run.

## Acceptance Criteria

- `POST /translate` translates through local Ollama using `translategemma:latest`.
- CLI and MCP translation calls return behavior consistent with `POST /translate`.
- The prompt builder preserves the exact TranslateGemma format, including the required blank-line separation before source text.
- Unsupported language codes are rejected before calling Ollama.
- Empty text is rejected before calling Ollama.
- `/languages` and MCP `list_languages()` expose the supported language table.
- `/health` and MCP `health()` report useful local Ollama/model status without leaking translation content.
