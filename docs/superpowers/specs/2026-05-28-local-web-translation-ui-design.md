# Local Web Translation UI Design

## Goal

Add a local browser-based translation workbench to the existing FastAPI service. The UI should make the local Ollama TranslateGemma service easy to use from a browser without adding a frontend build system or duplicating translation logic.

## Scope

The first version is a practical workbench:

- Text input for source text.
- Source and target language selectors with search/filter support.
- Swap languages action.
- Translate action with loading and disabled states.
- Translation result display.
- Copy result action.
- Health/status display for the local service, model, and Ollama.
- Clear user-facing error messages from API failures.

Out of scope for this version:

- Translation history.
- Favorites.
- Batch translation.
- Authentication.
- Remote hosting.
- Node, npm, React, Vite, or any frontend build step.

## Architecture

The Web UI is served by the existing FastAPI app.

- `GET /` returns the workbench HTML.
- Static assets are served from a package-local directory, for example `translate_service/web/static/`.
- The browser calls the existing HTTP API:
  - `GET /languages`
  - `GET /health`
  - `POST /translate`

The backend translation path remains unchanged. The Web UI is a client of the API, not a separate translation implementation.

## UI Behavior

On page load:

1. Fetch `/languages` and populate source/target controls.
2. Fetch `/health` and display service status.
3. Default language choices should match the service defaults where possible, with English to Chinese as the expected common default.

On translate:

1. Validate that text is non-empty before calling the API.
2. Disable the translate button while the request is in flight.
3. Send `{ "text": ..., "source_lang": ..., "target_lang": ... }` to `/translate`.
4. Display the returned translation.
5. Show API error `message` values when present.

On swap:

1. Swap source and target language selections.
2. Leave the input text and result text unchanged in the first version.

On copy:

1. Copy the translation result to the clipboard.
2. Show a short success or failure status message.

## Design Direction

The UI should feel like a quiet local utility, not a marketing page:

- Dense but readable layout.
- Fast access to input and output.
- Clear controls.
- Responsive enough for desktop and narrow browser windows.
- No decorative hero page.

## Error Handling

The UI should handle:

- Empty text.
- Unsupported language.
- Ollama unavailable.
- Model errors.
- Timeout errors.
- Network or unexpected frontend failures.

Errors should be shown inline without replacing the whole page.

## Deployment Impact

The macOS installer and LaunchAgent continue to run the same FastAPI service. No new system dependency is required. Users who install the service can open:

```text
http://127.0.0.1:8000/
```

No changes are required for CLI or MCP usage.

## Testing

Automated tests should cover:

- `GET /` returns HTML.
- Static CSS and JavaScript assets are served.
- The HTML includes expected root elements and asset references.
- Existing `/translate`, `/languages`, and `/health` behavior remains intact.

Manual or smoke verification should cover:

- Starting the local server.
- Opening the web UI.
- Confirming language loading and health display.
- Performing a real translation when Ollama and `translategemma:latest` are available.
