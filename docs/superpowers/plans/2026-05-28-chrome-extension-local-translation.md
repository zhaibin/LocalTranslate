# Chrome Extension Local Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Chrome Manifest V3 extension that translates selected webpage text and manual popup input through the existing local HTTP translation service.

**Architecture:** The extension lives in `chrome_extension/` as plain HTML/CSS/JavaScript with no build step. `background.js` owns right-click translation, settings reads, local API calls, content-script injection, and fallback result-page routing; content scripts only render overlays; extension pages call the local API from extension contexts using manifest host permissions.

**Tech Stack:** Chrome Manifest V3, plain JavaScript, Chrome extension APIs (`contextMenus`, `storage`, `scripting`, `tabs`), HTML/CSS, pytest static tests.

---

## File Structure

- Create `chrome_extension/manifest.json`
  - Declares Manifest V3 metadata, permissions, host permissions, background service worker, popup action, options page, and icons.
- Create `chrome_extension/background.js`
  - Defines defaults, settings helpers, API helpers, context menu lifecycle, content-script messaging, fallback storage, and runtime message handlers.
- Create `chrome_extension/content_script.js`
  - Renders and updates the in-page overlay. It never calls the local HTTP service.
- Create `chrome_extension/popup.html`
  - Popup manual translation UI.
- Create `chrome_extension/popup.js`
  - Popup settings/language loading, translation, copy, swap, and errors.
- Create `chrome_extension/options.html`
  - Options UI for service URL, default source language, default target language, service testing, and reset.
- Create `chrome_extension/options.js`
  - Options settings persistence, validation, `/health`, and `/languages`.
- Create `chrome_extension/result.html`
  - Fallback result page for restricted pages or injection failures.
- Create `chrome_extension/result.js`
  - Reads latest context-menu result from `chrome.storage.session`, renders it, and supports copy.
- Create `chrome_extension/styles.css`
  - Shared styling for popup, options, and result extension pages.
- Create `chrome_extension/icons/icon16.svg`, `chrome_extension/icons/icon32.svg`, `chrome_extension/icons/icon48.svg`, `chrome_extension/icons/icon128.svg`
  - Simple local extension icons.
- Create `tests/test_chrome_extension.py`
  - Static tests for manifest, required files, permissions, and important implementation markers.
- Modify `README.md`
  - Add local Chrome extension usage notes.

---

### Task 1: Add Static Extension Contract Tests

**Files:**
- Create: `tests/test_chrome_extension.py`

- [ ] **Step 1: Write failing manifest and file tests**

Create `tests/test_chrome_extension.py`:

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "chrome_extension"


def read_manifest():
    return json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_v3_contract():
    manifest = read_manifest()

    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "Local Translate"
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["action"]["default_popup"] == "popup.html"
    assert manifest["options_page"] == "options.html"


def test_manifest_permissions_cover_local_service_and_extension_apis():
    manifest = read_manifest()

    assert set(manifest["permissions"]) >= {
        "contextMenus",
        "storage",
        "activeTab",
        "scripting",
    }
    assert "http://127.0.0.1:*/*" in manifest["host_permissions"]
    assert "http://localhost:*/*" in manifest["host_permissions"]


def test_expected_extension_files_exist():
    expected_files = [
        "manifest.json",
        "background.js",
        "content_script.js",
        "popup.html",
        "popup.js",
        "options.html",
        "options.js",
        "result.html",
        "result.js",
        "styles.css",
        "icons/icon16.svg",
        "icons/icon32.svg",
        "icons/icon48.svg",
        "icons/icon128.svg",
    ]

    for relative_path in expected_files:
        assert (EXTENSION_DIR / relative_path).is_file(), relative_path


def test_content_script_does_not_call_local_api_directly():
    content = (EXTENSION_DIR / "content_script.js").read_text(encoding="utf-8")

    assert "fetch(" not in content
    assert "/translate" not in content
    assert "/languages" not in content
    assert "/health" not in content


def test_background_contains_context_menu_and_fallback_storage_flow():
    background = (EXTENSION_DIR / "background.js").read_text(encoding="utf-8")

    assert "chrome.contextMenus.create" in background
    assert "chrome.contextMenus.onClicked.addListener" in background
    assert "chrome.scripting.executeScript" in background
    assert "chrome.storage.local" in background
    assert "chrome.storage.session" in background
    assert "result.html" in background
    assert "/translate" in background
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py -q
```

Expected: FAIL because `chrome_extension/manifest.json` does not exist.

- [ ] **Step 3: Commit failing tests**

Run:

```bash
git add tests/test_chrome_extension.py
git commit -m "test: add chrome extension contract tests"
```

---

### Task 2: Add Manifest, Icons, and Background Translation Core

**Files:**
- Create: `chrome_extension/manifest.json`
- Create: `chrome_extension/background.js`
- Create: `chrome_extension/icons/icon16.svg`
- Create: `chrome_extension/icons/icon32.svg`
- Create: `chrome_extension/icons/icon48.svg`
- Create: `chrome_extension/icons/icon128.svg`
- Test: `tests/test_chrome_extension.py`

- [ ] **Step 1: Create manifest**

Create `chrome_extension/manifest.json`:

```json
{
  "manifest_version": 3,
  "name": "Local Translate",
  "description": "Translate selected text with a local Ollama translation service.",
  "version": "0.1.0",
  "permissions": ["contextMenus", "storage", "activeTab", "scripting"],
  "host_permissions": ["http://127.0.0.1:*/*", "http://localhost:*/*"],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_title": "Local Translate",
    "default_popup": "popup.html"
  },
  "options_page": "options.html",
  "icons": {
    "16": "icons/icon16.svg",
    "32": "icons/icon32.svg",
    "48": "icons/icon48.svg",
    "128": "icons/icon128.svg"
  }
}
```

- [ ] **Step 2: Create icons**

Create each icon file with the matching size. Use this content for `chrome_extension/icons/icon16.svg`, changing both `width` and `height` to `16`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 64 64" role="img" aria-label="Local Translate">
  <rect width="64" height="64" rx="12" fill="#1f6feb"/>
  <path d="M15 18h34v8H37c-1 5-3 9-6 13 3 2 6 4 10 5l-4 6c-4-2-8-4-11-7-3 3-6 5-10 7l-4-6c4-1 7-3 10-5-2-3-4-6-5-10h8c1 2 2 4 4 6 2-3 4-6 5-9H15z" fill="#fff"/>
  <path d="M41 43h10l2 6h6L48 19h-5L32 49h6zm2-6 3-9 3 9z" fill="#dff6ff"/>
</svg>
```

Create `icon32.svg`, `icon48.svg`, and `icon128.svg` with the same SVG and matching `width`/`height` values `32`, `48`, and `128`.

- [ ] **Step 3: Create background service worker**

Create `chrome_extension/background.js`:

```javascript
const DEFAULT_SETTINGS = {
  serviceUrl: "http://127.0.0.1:8000",
  sourceLang: "en",
  targetLang: "zh",
};

const CONTEXT_MENU_ID = "local-translate-selection";
const SESSION_RESULT_KEY = "latestContextMenuResult";

function normalizeServiceUrl(value) {
  const raw = (value || DEFAULT_SETTINGS.serviceUrl).trim().replace(/\/+$/, "");
  const url = new URL(raw);
  if (url.protocol !== "http:") {
    throw new Error("Service URL must use http.");
  }
  if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
    throw new Error("Service URL must point to 127.0.0.1 or localhost.");
  }
  return url.toString().replace(/\/+$/, "");
}

async function getSettings() {
  const stored = await chrome.storage.local.get(DEFAULT_SETTINGS);
  return {
    serviceUrl: normalizeServiceUrl(stored.serviceUrl),
    sourceLang: stored.sourceLang || DEFAULT_SETTINGS.sourceLang,
    targetLang: stored.targetLang || DEFAULT_SETTINGS.targetLang,
  };
}

async function parseApiError(response) {
  try {
    const body = await response.json();
    return body.message || `Request failed with status ${response.status}`;
  } catch (_error) {
    return `Request failed with status ${response.status}`;
  }
}

async function requestJson(path, options = {}) {
  const settings = await getSettings();
  const response = await fetch(`${settings.serviceUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

async function translateText(text, sourceLang, targetLang) {
  const settings = await getSettings();
  const trimmed = (text || "").trim();
  if (!trimmed) {
    throw new Error("Select text to translate.");
  }
  return requestJson("/translate", {
    method: "POST",
    body: JSON.stringify({
      text: trimmed,
      source_lang: sourceLang || settings.sourceLang,
      target_lang: targetLang || settings.targetLang,
    }),
  });
}

async function sendToTab(tabId, message) {
  try {
    await chrome.tabs.sendMessage(tabId, message);
    return true;
  } catch (_error) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content_script.js"],
    });
    await chrome.tabs.sendMessage(tabId, message);
    return true;
  }
}

async function openFallback(payload) {
  await chrome.storage.session.set({ [SESSION_RESULT_KEY]: payload });
  await chrome.tabs.create({ url: chrome.runtime.getURL("result.html") });
}

async function showResult(tabId, payload) {
  try {
    await sendToTab(tabId, { type: "LOCAL_TRANSLATE_RESULT", payload });
  } catch (_error) {
    await openFallback(payload);
  }
}

async function handleContextMenuClick(info, tab) {
  const tabId = tab && tab.id;
  const sourceText = info.selectionText || "";
  const loadingPayload = { status: "loading", sourceText };
  if (tabId) {
    try {
      await sendToTab(tabId, { type: "LOCAL_TRANSLATE_LOADING", payload: loadingPayload });
    } catch (_error) {
      /* Fall back after the translation finishes so the result page has useful content. */
    }
  }

  try {
    const translation = await translateText(sourceText);
    const payload = { status: "success", sourceText, translation };
    if (tabId) {
      await showResult(tabId, payload);
    } else {
      await openFallback(payload);
    }
  } catch (error) {
    const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
    const payload = {
      status: "error",
      sourceText,
      error: error.message || "Translation failed.",
      serviceUrl: settings.serviceUrl || DEFAULT_SETTINGS.serviceUrl,
    };
    if (tabId) {
      await showResult(tabId, payload);
    } else {
      await openFallback(payload);
    }
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: CONTEXT_MENU_ID,
    title: "Translate selection locally",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === CONTEXT_MENU_ID) {
    handleContextMenuClick(info, tab);
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "LOCAL_TRANSLATE_GET_SETTINGS") {
    getSettings().then(sendResponse).catch((error) => sendResponse({ error: error.message }));
    return true;
  }
  if (message.type === "LOCAL_TRANSLATE_TRANSLATE") {
    translateText(message.text, message.sourceLang, message.targetLang)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message.type === "LOCAL_TRANSLATE_LANGUAGES") {
    requestJson("/languages")
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message.type === "LOCAL_TRANSLATE_HEALTH") {
    requestJson("/health")
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  return false;
});
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py -q
```

Expected: FAIL because popup, options, result, content script, and styles files do not exist yet.

- [ ] **Step 5: Commit manifest and background core**

Run:

```bash
git add chrome_extension/manifest.json chrome_extension/background.js chrome_extension/icons tests/test_chrome_extension.py
git commit -m "feat: add chrome extension manifest and background core"
```

---

### Task 3: Add Page Overlay and Fallback Result Page

**Files:**
- Create: `chrome_extension/content_script.js`
- Create: `chrome_extension/result.html`
- Create: `chrome_extension/result.js`
- Create: `chrome_extension/styles.css`
- Test: `tests/test_chrome_extension.py`

- [ ] **Step 1: Create content script overlay**

Create `chrome_extension/content_script.js`:

```javascript
const OVERLAY_ID = "local-translate-overlay";
const STYLE_ID = "local-translate-overlay-style";

function ensureOverlayStyle() {
  if (document.getElementById(STYLE_ID)) {
    return;
  }
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    #${OVERLAY_ID} {
      position: fixed;
      z-index: 2147483647;
      right: 20px;
      bottom: 20px;
      width: min(360px, calc(100vw - 40px));
      max-height: min(420px, calc(100vh - 40px));
      overflow: auto;
      box-sizing: border-box;
      padding: 14px;
      border: 1px solid #d0d7de;
      border-radius: 8px;
      background: #ffffff;
      color: #1f2328;
      box-shadow: 0 16px 40px rgba(31, 35, 40, 0.2);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    #${OVERLAY_ID} .lt-header {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      margin-bottom: 10px;
      font-weight: 700;
    }
    #${OVERLAY_ID} .lt-body {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    #${OVERLAY_ID} .lt-error {
      color: #b42318;
    }
    #${OVERLAY_ID} .lt-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 12px;
    }
    #${OVERLAY_ID} button {
      border: 1px solid #d0d7de;
      border-radius: 6px;
      background: #f6f8fa;
      color: #1f2328;
      padding: 6px 10px;
      cursor: pointer;
      font: inherit;
    }
  `;
  document.documentElement.appendChild(style);
}

function getTranslationText(payload) {
  return payload.translation && payload.translation.translation
    ? payload.translation.translation
    : "";
}

async function copyText(text, statusNode) {
  try {
    await navigator.clipboard.writeText(text);
    statusNode.textContent = "Copied.";
  } catch (_error) {
    statusNode.textContent = "Copy failed. Select the text and copy manually.";
  }
}

function renderOverlay(payload) {
  ensureOverlayStyle();
  const existing = document.getElementById(OVERLAY_ID);
  if (existing) {
    existing.remove();
  }

  const overlay = document.createElement("section");
  overlay.id = OVERLAY_ID;
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-live", "polite");

  const header = document.createElement("div");
  header.className = "lt-header";
  const title = document.createElement("span");
  title.textContent = "Local Translate";
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => overlay.remove());
  header.append(title, close);

  const body = document.createElement("div");
  body.className = "lt-body";

  const actions = document.createElement("div");
  actions.className = "lt-actions";
  const status = document.createElement("span");

  if (payload.status === "loading") {
    body.textContent = "Translating...";
  } else if (payload.status === "success") {
    const text = getTranslationText(payload);
    body.textContent = text;
    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy";
    copy.addEventListener("click", () => copyText(text, status));
    actions.append(status, copy);
  } else {
    body.classList.add("lt-error");
    body.textContent = payload.error || "Translation failed.";
  }

  overlay.append(header, body, actions);
  document.documentElement.appendChild(overlay);
}

chrome.runtime.onMessage.addListener((message) => {
  if (
    message.type === "LOCAL_TRANSLATE_LOADING" ||
    message.type === "LOCAL_TRANSLATE_RESULT"
  ) {
    renderOverlay(message.payload || {});
  }
});
```

- [ ] **Step 2: Create shared extension page styles**

Create `chrome_extension/styles.css`:

```css
:root {
  color-scheme: light;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #1f2328;
  background: #f6f8fa;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

.page {
  width: min(760px, 100vw);
  margin: 0 auto;
  padding: 18px;
}

.popup {
  width: 360px;
  min-height: 420px;
}

h1 {
  margin: 0 0 14px;
  font-size: 20px;
}

label {
  display: grid;
  gap: 6px;
  margin: 12px 0;
  font-weight: 600;
}

input,
select,
textarea {
  width: 100%;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  padding: 8px 10px;
  font: inherit;
  background: #ffffff;
  color: #1f2328;
}

textarea {
  min-height: 110px;
  resize: vertical;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

button {
  border: 1px solid #d0d7de;
  border-radius: 6px;
  background: #ffffff;
  color: #1f2328;
  padding: 8px 12px;
  cursor: pointer;
  font: inherit;
}

button.primary {
  border-color: #1f6feb;
  background: #1f6feb;
  color: #ffffff;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.message {
  min-height: 22px;
  margin: 10px 0;
  color: #57606a;
}

.message.error {
  color: #b42318;
}

.message.success {
  color: #1a7f37;
}

.result {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  min-height: 120px;
  padding: 10px;
  background: #ffffff;
}
```

- [ ] **Step 3: Create fallback result page**

Create `chrome_extension/result.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Local Translate Result</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <main class="page">
      <h1>Local Translate</h1>
      <section>
        <label>
          Selected text
          <textarea id="sourceText" readonly></textarea>
        </label>
        <label>
          Result
          <div id="resultText" class="result" role="status"></div>
        </label>
      </section>
      <div class="actions">
        <button id="copyButton" type="button">Copy</button>
        <button id="closeButton" type="button">Close</button>
      </div>
      <p id="message" class="message"></p>
    </main>
    <script src="result.js" defer></script>
  </body>
</html>
```

Create `chrome_extension/result.js`:

```javascript
const SESSION_RESULT_KEY = "latestContextMenuResult";

const elements = {
  sourceText: document.querySelector("#sourceText"),
  resultText: document.querySelector("#resultText"),
  copyButton: document.querySelector("#copyButton"),
  closeButton: document.querySelector("#closeButton"),
  message: document.querySelector("#message"),
};

function setMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = `message ${type}`.trim();
}

function resultText(payload) {
  if (payload.status === "success") {
    return payload.translation && payload.translation.translation
      ? payload.translation.translation
      : "";
  }
  return payload.error || "Translation failed.";
}

async function copyResult() {
  const text = elements.resultText.textContent;
  if (!text) {
    setMessage("No translation to copy.", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    setMessage("Copied.", "success");
  } catch (_error) {
    setMessage("Copy failed. Select the result and copy manually.", "error");
  }
}

async function init() {
  const stored = await chrome.storage.session.get(SESSION_RESULT_KEY);
  const payload = stored[SESSION_RESULT_KEY];
  if (!payload) {
    elements.resultText.textContent = "No translation result is available.";
    elements.copyButton.disabled = true;
    return;
  }

  elements.sourceText.value = payload.sourceText || "";
  elements.resultText.textContent = resultText(payload);
  if (payload.status === "error") {
    setMessage(`Check the local service: ${payload.serviceUrl || "http://127.0.0.1:8000"}`, "error");
  }
}

elements.copyButton.addEventListener("click", copyResult);
elements.closeButton.addEventListener("click", () => window.close());
document.addEventListener("DOMContentLoaded", init);
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py -q
```

Expected: FAIL because popup and options files do not exist yet.

- [ ] **Step 5: Commit overlay and fallback page**

Run:

```bash
git add chrome_extension/content_script.js chrome_extension/result.html chrome_extension/result.js chrome_extension/styles.css
git commit -m "feat: add translation overlay and fallback result page"
```

---

### Task 4: Add Popup and Options Pages

**Files:**
- Create: `chrome_extension/popup.html`
- Create: `chrome_extension/popup.js`
- Create: `chrome_extension/options.html`
- Create: `chrome_extension/options.js`
- Test: `tests/test_chrome_extension.py`

- [ ] **Step 1: Create popup UI and behavior**

Create `chrome_extension/popup.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Local Translate</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <main class="page popup">
      <h1>Local Translate</h1>
      <label>
        Text
        <textarea id="sourceText"></textarea>
      </label>
      <label>
        From
        <select id="sourceLang"></select>
      </label>
      <label>
        To
        <select id="targetLang"></select>
      </label>
      <div class="actions">
        <button id="swapButton" type="button">Swap</button>
        <button id="translateButton" class="primary" type="button">Translate</button>
      </div>
      <label>
        Translation
        <textarea id="resultText" readonly></textarea>
      </label>
      <div class="actions">
        <button id="copyButton" type="button">Copy</button>
        <button id="optionsButton" type="button">Options</button>
      </div>
      <p id="message" class="message"></p>
    </main>
    <script src="popup.js" defer></script>
  </body>
</html>
```

Create `chrome_extension/popup.js`:

```javascript
const DEFAULT_SETTINGS = {
  serviceUrl: "http://127.0.0.1:8000",
  sourceLang: "en",
  targetLang: "zh",
};

const elements = {
  sourceText: document.querySelector("#sourceText"),
  resultText: document.querySelector("#resultText"),
  sourceLang: document.querySelector("#sourceLang"),
  targetLang: document.querySelector("#targetLang"),
  swapButton: document.querySelector("#swapButton"),
  translateButton: document.querySelector("#translateButton"),
  copyButton: document.querySelector("#copyButton"),
  optionsButton: document.querySelector("#optionsButton"),
  message: document.querySelector("#message"),
};

function setMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = `message ${type}`.trim();
}

function sendMessage(message) {
  return chrome.runtime.sendMessage(message);
}

function renderLanguages(languages, settings) {
  for (const select of [elements.sourceLang, elements.targetLang]) {
    select.replaceChildren(
      ...languages.map((language) => {
        const option = document.createElement("option");
        option.value = language.code;
        option.textContent = `${language.name} (${language.code})`;
        return option;
      }),
    );
  }
  elements.sourceLang.value = settings.sourceLang;
  elements.targetLang.value = settings.targetLang;
}

async function loadLanguages() {
  const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
  const response = await sendMessage({ type: "LOCAL_TRANSLATE_LANGUAGES" });
  if (!response.ok) {
    throw new Error(response.error || "Could not load languages.");
  }
  renderLanguages(response.result.languages, settings);
}

async function translate() {
  const text = elements.sourceText.value.trim();
  if (!text) {
    setMessage("Enter text to translate.", "error");
    return;
  }
  elements.translateButton.disabled = true;
  setMessage("Translating...");
  const response = await sendMessage({
    type: "LOCAL_TRANSLATE_TRANSLATE",
    text,
    sourceLang: elements.sourceLang.value,
    targetLang: elements.targetLang.value,
  });
  elements.translateButton.disabled = false;
  if (!response.ok) {
    setMessage(response.error || "Translation failed.", "error");
    return;
  }
  elements.resultText.value = response.result.translation;
  setMessage("Translation complete.", "success");
}

async function copyResult() {
  if (!elements.resultText.value) {
    setMessage("No translation to copy.", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(elements.resultText.value);
    setMessage("Copied.", "success");
  } catch (_error) {
    setMessage("Copy failed. Select the translation and copy manually.", "error");
  }
}

function swapLanguages() {
  const source = elements.sourceLang.value;
  elements.sourceLang.value = elements.targetLang.value;
  elements.targetLang.value = source;
}

async function init() {
  elements.translateButton.addEventListener("click", translate);
  elements.copyButton.addEventListener("click", copyResult);
  elements.swapButton.addEventListener("click", swapLanguages);
  elements.optionsButton.addEventListener("click", () => chrome.runtime.openOptionsPage());
  try {
    await loadLanguages();
  } catch (error) {
    setMessage(error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
```

- [ ] **Step 2: Create options UI and behavior**

Create `chrome_extension/options.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Local Translate Options</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <main class="page">
      <h1>Local Translate Options</h1>
      <label>
        Service URL
        <input id="serviceUrl" type="url" />
      </label>
      <label>
        Default source language
        <select id="sourceLang"></select>
      </label>
      <label>
        Default target language
        <select id="targetLang"></select>
      </label>
      <div class="actions">
        <button id="saveButton" class="primary" type="button">Save</button>
        <button id="resetButton" type="button">Reset</button>
        <button id="testButton" type="button">Test connection</button>
        <button id="reloadLanguagesButton" type="button">Reload languages</button>
      </div>
      <p id="message" class="message"></p>
    </main>
    <script src="options.js" defer></script>
  </body>
</html>
```

Create `chrome_extension/options.js`:

```javascript
const DEFAULT_SETTINGS = {
  serviceUrl: "http://127.0.0.1:8000",
  sourceLang: "en",
  targetLang: "zh",
};

const elements = {
  serviceUrl: document.querySelector("#serviceUrl"),
  sourceLang: document.querySelector("#sourceLang"),
  targetLang: document.querySelector("#targetLang"),
  saveButton: document.querySelector("#saveButton"),
  resetButton: document.querySelector("#resetButton"),
  testButton: document.querySelector("#testButton"),
  reloadLanguagesButton: document.querySelector("#reloadLanguagesButton"),
  message: document.querySelector("#message"),
};

function setMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = `message ${type}`.trim();
}

function validateServiceUrl(value) {
  const url = new URL(value.trim().replace(/\/+$/, ""));
  if (url.protocol !== "http:") {
    throw new Error("Service URL must use http.");
  }
  if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
    throw new Error("Service URL must point to 127.0.0.1 or localhost.");
  }
  return url.toString().replace(/\/+$/, "");
}

function renderLanguages(languages, settings) {
  for (const select of [elements.sourceLang, elements.targetLang]) {
    select.replaceChildren(
      ...languages.map((language) => {
        const option = document.createElement("option");
        option.value = language.code;
        option.textContent = `${language.name} (${language.code})`;
        return option;
      }),
    );
  }
  elements.sourceLang.value = settings.sourceLang;
  elements.targetLang.value = settings.targetLang;
}

async function fetchJson(serviceUrl, path) {
  const response = await fetch(`${serviceUrl}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json();
}

async function loadLanguages() {
  const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
  const serviceUrl = validateServiceUrl(elements.serviceUrl.value || settings.serviceUrl);
  const body = await fetchJson(serviceUrl, "/languages");
  renderLanguages(body.languages, settings);
}

async function loadSettings() {
  const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
  elements.serviceUrl.value = settings.serviceUrl;
  try {
    await loadLanguages();
  } catch (error) {
    renderLanguages(
      [
        { code: "en", name: "English" },
        { code: "zh", name: "Chinese" },
      ],
      settings,
    );
    setMessage(`Could not load languages: ${error.message}`, "error");
  }
}

async function saveSettings() {
  try {
    const serviceUrl = validateServiceUrl(elements.serviceUrl.value);
    await chrome.storage.local.set({
      serviceUrl,
      sourceLang: elements.sourceLang.value,
      targetLang: elements.targetLang.value,
    });
    setMessage("Options saved.", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function resetSettings() {
  await chrome.storage.local.set(DEFAULT_SETTINGS);
  await loadSettings();
  setMessage("Options reset.", "success");
}

async function testConnection() {
  try {
    const serviceUrl = validateServiceUrl(elements.serviceUrl.value);
    const body = await fetchJson(serviceUrl, "/health");
    setMessage(`Service ${body.status}: ${body.model || "unknown model"}`, "success");
  } catch (error) {
    setMessage(`Connection failed: ${error.message}`, "error");
  }
}

async function reloadLanguages() {
  try {
    await loadLanguages();
    setMessage("Languages reloaded.", "success");
  } catch (error) {
    setMessage(`Could not reload languages: ${error.message}`, "error");
  }
}

function bindEvents() {
  elements.saveButton.addEventListener("click", saveSettings);
  elements.resetButton.addEventListener("click", resetSettings);
  elements.testButton.addEventListener("click", testConnection);
  elements.reloadLanguagesButton.addEventListener("click", reloadLanguages);
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadSettings();
});
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit popup and options pages**

Run:

```bash
git add chrome_extension/popup.html chrome_extension/popup.js chrome_extension/options.html chrome_extension/options.js
git commit -m "feat: add chrome extension popup and options"
```

---

### Task 5: Document and Run Full Verification

**Files:**
- Modify: `README.md`
- Test: `tests/test_chrome_extension.py`

- [ ] **Step 1: Add README documentation test**

Append this test to `tests/test_chrome_extension.py`:

```python
def test_readme_documents_chrome_extension_usage():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Chrome Extension" in readme
    assert "chrome_extension/" in readme
    assert "Load unpacked" in readme
    assert "http://127.0.0.1:8000" in readme
```

- [ ] **Step 2: Run README test to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_chrome_extension.py::test_readme_documents_chrome_extension_usage -q
```

Expected: FAIL because README does not document the Chrome extension yet.

- [ ] **Step 3: Update README**

Add this section to `README.md` after the local web UI/API usage section:

```markdown
## Chrome Extension

The repository includes a local Chrome extension in `chrome_extension/`. It translates selected webpage text through the local HTTP service and provides a popup for manual translation.

Before loading the extension, start the local service:

```bash
.venv/bin/translate serve
```

Then open Chrome extensions, enable Developer mode, choose **Load unpacked**, and select the `chrome_extension/` directory.

Defaults:

- Service URL: `http://127.0.0.1:8000`
- Source language: `en`
- Target language: `zh`

Use the extension options page to change the service URL or default languages. The extension does not save translation history.
```

- [ ] **Step 4: Run full test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 5: Run linter**

Run:

```bash
.venv/bin/ruff check .
```

Expected: PASS.

- [ ] **Step 6: Manual Chrome smoke verification**

Run the local service:

```bash
.venv/bin/translate serve
```

In Chrome:

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click **Load unpacked** and select `chrome_extension/`.
4. Open a normal webpage.
5. Select text and choose **Translate selection locally** from the context menu.
6. Confirm the overlay shows loading and then the translation.
7. Click **Copy** and confirm the translated text is on the clipboard.
8. Open the extension popup, enter text, translate, and copy.
9. Open the options page, test connection, change languages, save, and translate again.
10. Stop the local service and confirm the extension shows a clear error.

Expected: All manual checks pass, except real translation depends on Ollama and `translategemma:latest` being available.

- [ ] **Step 7: Commit docs and verification updates**

Run:

```bash
git add README.md tests/test_chrome_extension.py
git commit -m "docs: document chrome extension usage"
```

---

## Self-Review

- Spec coverage: The plan covers Manifest V3 extension files, right-click translation, page overlay, result fallback, popup, options, local storage settings, session fallback data, static tests, no backend API changes, no history, and no build tooling.
- Placeholder scan: The plan contains no deferred implementation markers.
- Type consistency: Message names use `LOCAL_TRANSLATE_*` consistently; settings keys are `serviceUrl`, `sourceLang`, and `targetLang`; fallback storage key is `latestContextMenuResult`.
