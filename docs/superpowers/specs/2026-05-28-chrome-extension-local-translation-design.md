# Chrome Extension Local Translation Design

## Goal

Add a Chrome extension that calls the existing local translation HTTP service. The extension should make selected webpage text easy to translate through the local Ollama-backed service while keeping the first version small, local-first, and free of frontend build tooling.

## Scope

The first version includes:

- A Chrome Manifest V3 extension under `chrome_extension/`.
- A right-click menu item for translating selected webpage text.
- A page overlay for showing loading, translation results, errors, copy, and close actions.
- A fallback extension result page for restricted pages or injection failures.
- A popup for manual text translation.
- An options page for service URL and default language settings.
- Static tests for the extension manifest and expected files.

Out of scope for the first version:

- Translation history.
- Whole-page translation.
- Automatic language detection.
- Backend API changes.
- npm, React, Vite, or any frontend build step.
- Publishing to the Chrome Web Store.

## Existing Service Contract

The extension uses the existing HTTP API:

```text
GET /health
GET /languages
POST /translate
```

`POST /translate` receives:

```json
{
  "text": "Hello",
  "source_lang": "en",
  "target_lang": "zh"
}
```

The local service defaults already match the extension defaults:

```text
Service URL: http://127.0.0.1:8000
Source language: en
Target language: zh
```

The FastAPI app does not currently configure CORS. The extension should therefore make local API requests from the extension background service worker or extension pages, using Chrome host permissions. Content scripts should not call the local API directly.

## Architecture

The extension is a static Manifest V3 extension:

```text
chrome_extension/
  manifest.json
  background.js
  content_script.js
  popup.html
  popup.js
  options.html
  options.js
  result.html
  result.js
  styles.css
  icons/
```

Responsibilities:

- `background.js`: creates the context menu, reads stored settings, calls the local API, injects or messages the content script, and opens the fallback result page when needed.
- `content_script.js`: displays the in-page translation overlay and handles overlay copy/close actions.
- `popup.html` and `popup.js`: provide manual input translation with temporary source and target language choices.
- `options.html` and `options.js`: configure service URL, default source language, default target language, connection testing, and language reload.
- `result.html` and `result.js`: display the latest context-menu translation result or error when page overlay display is unavailable.
- `styles.css`: shared styles for extension pages. Page overlay styles are injected by `content_script.js` to avoid depending on the host page.

## Manifest Permissions

The manifest should declare:

```json
{
  "manifest_version": 3,
  "permissions": ["contextMenus", "storage", "activeTab", "scripting"],
  "host_permissions": [
    "http://127.0.0.1:*/*",
    "http://localhost:*/*"
  ]
}
```

`contextMenus` supports the selected-text right-click entry. `storage` stores local settings. `activeTab` and `scripting` support injecting or waking the content script for the current tab. Host permissions allow extension contexts to call the local service.

Settings should use `chrome.storage.local`, not `chrome.storage.sync`, because the service URL is machine-local and should not be synchronized across computers.

Fallback result data should use `chrome.storage.session` when available. This keeps the latest context-menu result available to `result.html` without persisting translation history to disk. If `chrome.storage.session` is unavailable, the implementation may keep an in-memory value in the service worker and open `result.html` immediately after writing it.

## Right-Click Translation Flow

1. User selects text on a normal webpage.
2. User clicks the extension context menu item.
3. `background.js` receives `contextMenus.onClicked` with selected text.
4. `background.js` reads settings from `chrome.storage.local`.
5. `background.js` sends a loading message to the current tab, injecting `content_script.js` first if needed.
6. `background.js` calls `POST {serviceUrl}/translate`.
7. On success, `background.js` sends the translation result to the content script.
8. The content script shows the result in an overlay with copy and close controls.
9. If script injection or messaging fails, `background.js` writes the latest result or error to session storage and opens `result.html`.

The content script is presentation-only. It does not call `/translate`, `/languages`, or `/health`.

## Popup Flow

The popup is a backup manual translation surface:

1. User opens the extension popup.
2. Popup loads service URL and default languages from `chrome.storage.local`.
3. Popup loads languages from `/languages` using an extension-page API call.
4. User enters text and can temporarily adjust source and target languages.
5. Popup calls the local `/translate` endpoint from the extension page context.
6. Popup displays the translation and copy action.

Popup state is not persisted as history. It may keep only the current open popup session state.

## Options Flow

The options page provides:

- Service URL, defaulting to `http://127.0.0.1:8000`.
- Default source language, defaulting to `en`.
- Default target language, defaulting to `zh`.
- A connection test that calls `/health`.
- A language reload action that calls `/languages`.
- Save and reset actions.

The options page should show clear validation errors for malformed service URLs and failed service checks.

## Result Fallback

`result.html` is used when the page overlay cannot be shown. Typical cases include restricted browser pages, extension pages, Chrome Web Store pages, file pages without permission, or content script injection failures.

The fallback page should show:

- The selected source text if available.
- The translated text or error message.
- Copy action for successful translations.
- A short hint to check the local service when the error is network-related.

The fallback reads the latest context-menu result from `chrome.storage.session`. The fallback exists so a context-menu request never fails silently, while still avoiding durable translation history.

## Error Handling

The extension should handle:

- Empty selected text or empty popup input.
- Service not running.
- Invalid service URL.
- `/health` degraded or unreachable.
- `/languages` load failure.
- Unsupported language responses from the backend.
- Ollama unavailable, model errors, and timeout responses from the backend.
- Restricted pages and content script injection failures.
- Clipboard copy failures.

Backend error responses with a `message` field should display that message. Network failures should mention the configured service URL so the user knows what to check.

## Testing

Automated tests should stay lightweight:

- Validate `chrome_extension/manifest.json` parses as JSON.
- Assert `manifest_version` is `3`.
- Assert `background.service_worker` is present.
- Assert required permissions include `contextMenus`, `storage`, `activeTab`, and `scripting`.
- Assert host permissions include `http://127.0.0.1:*/*` and `http://localhost:*/*`.
- Assert `action` and `options_page` are present.
- Assert expected extension files exist.
- Keep existing backend API and Web UI tests passing.

Manual verification should cover:

1. Start the local service with `.venv/bin/translate serve`.
2. Confirm `http://127.0.0.1:8000/health` is reachable.
3. Load `chrome_extension/` as an unpacked Chrome extension.
4. Select text on a normal webpage and use the right-click translation menu.
5. Confirm the in-page overlay shows loading and then the translation.
6. Confirm overlay copy and close controls work.
7. Confirm the fallback result page appears when overlay injection is unavailable.
8. Confirm popup manual translation works.
9. Confirm options save service URL and default language settings.
10. Stop the service and confirm the extension shows a clear failure message.

## Acceptance Criteria

- The extension calls the existing local HTTP service without adding backend endpoints.
- Selected webpage text can be translated from the Chrome context menu.
- Normal pages show translation results in an in-page overlay.
- Restricted or failed injection cases fall back to `result.html`.
- Popup manual translation works.
- Options configure service URL and default languages using `chrome.storage.local`.
- No translation history is saved.
- No npm or frontend build step is introduced.
- Existing backend tests continue to pass.
