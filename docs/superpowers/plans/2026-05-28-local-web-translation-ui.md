# Local Web Translation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a browser-based local translation workbench served by the existing FastAPI app.

**Architecture:** The FastAPI app will serve `GET /` plus package-local static assets. The browser UI will call the existing `/languages`, `/health`, and `/translate` endpoints so translation logic stays in `TranslationService`.

**Tech Stack:** FastAPI, Starlette static files, package resource files, plain HTML/CSS/JavaScript, pytest, ruff.

---

## File Structure

- Create `translate_service/web/__init__.py`
  - Marks the web asset package.
- Create `translate_service/web/static/index.html`
  - Browser workbench structure and asset references.
- Create `translate_service/web/static/styles.css`
  - Quiet local utility styling with responsive layout.
- Create `translate_service/web/static/app.js`
  - Fetch languages/health, translate, swap, copy, and error handling.
- Modify `translate_service/api/app.py`
  - Mount static assets and serve `GET /`.
- Modify `tests/test_api.py`
  - Add tests for HTML and static asset serving.
- Modify `README.md`
  - Mention the local web UI URL in usage/deployment docs.

---

### Task 1: Serve Web UI from FastAPI

**Files:**
- Create: `translate_service/web/__init__.py`
- Create: `translate_service/web/static/index.html`
- Create: `translate_service/web/static/styles.css`
- Create: `translate_service/web/static/app.js`
- Modify: `translate_service/api/app.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add these tests to `tests/test_api.py`:

```python
def test_web_root_returns_translation_workbench_html():
    client = TestClient(create_app(FakeService()))

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<main id="app"' in response.text
    assert 'src="/static/app.js"' in response.text
    assert 'href="/static/styles.css"' in response.text


def test_web_static_assets_are_served():
    client = TestClient(create_app(FakeService()))

    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert "application/javascript" in js_response.headers["content-type"]
    assert "async function translateText" in js_response.text
    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert ".workbench" in css_response.text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Expected: the new tests fail because `/` and `/static/app.js` are not implemented.

- [ ] **Step 3: Add placeholder web assets**

Create `translate_service/web/__init__.py`:

```python
"""Package-local web assets for the browser translation workbench."""
```

Create `translate_service/web/static/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Local Translate</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <main id="app" class="workbench">
      <h1>Local Translate</h1>
      <p>Loading translation workbench...</p>
    </main>
    <script src="/static/app.js" defer></script>
  </body>
</html>
```

Create `translate_service/web/static/styles.css`:

```css
:root {
  color-scheme: light;
}

.workbench {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}
```

Create `translate_service/web/static/app.js`:

```javascript
async function translateText() {
  return null;
}
```

- [ ] **Step 4: Mount static assets and serve root**

Modify `translate_service/api/app.py`:

```python
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
```

Add module constants near imports:

```python
WEB_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"
WEB_INDEX_PATH = WEB_STATIC_DIR / "index.html"
```

In `create_app`, after setting `app.state.translation_service`, mount static assets and register the root route:

```python
    app.mount("/static", StaticFiles(directory=WEB_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def web_index():
        return FileResponse(WEB_INDEX_PATH)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Expected: all `tests/test_api.py` tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add translate_service/web translate_service/api/app.py tests/test_api.py
git commit -m "feat: serve local web translation UI"
```

---

### Task 2: Implement Translation Workbench UI

**Files:**
- Modify: `translate_service/web/static/index.html`
- Modify: `translate_service/web/static/styles.css`
- Modify: `translate_service/web/static/app.js`
- Test: `tests/test_api.py`

- [ ] **Step 1: Strengthen HTML/static tests**

Extend `test_web_root_returns_translation_workbench_html` in `tests/test_api.py`:

```python
    for expected in [
        'id="sourceText"',
        'id="sourceSearch"',
        'id="sourceLang"',
        'id="targetSearch"',
        'id="targetLang"',
        'id="swapLanguages"',
        'id="translateButton"',
        'id="copyButton"',
        'id="resultText"',
        'id="healthStatus"',
        'id="message"',
    ]:
        assert expected in response.text
```

Extend `test_web_static_assets_are_served`:

```python
    for expected in [
        "loadLanguages",
        "loadHealth",
        "swapLanguages",
        "copyResult",
        "renderLanguageOptions",
        "showMessage",
    ]:
        assert expected in js_response.text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Expected: new assertions fail until full UI markup and JavaScript are added.

- [ ] **Step 3: Replace HTML with full workbench markup**

Replace `translate_service/web/static/index.html` with:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Local Translate</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <main id="app" class="workbench">
      <header class="topbar">
        <div>
          <h1>Local Translate</h1>
          <p id="healthStatus" class="status">Checking service...</p>
        </div>
        <button id="refreshHealth" class="icon-button" type="button" title="Refresh status">Refresh</button>
      </header>

      <section class="language-bar" aria-label="Language controls">
        <label>
          <span>From</span>
          <input id="sourceSearch" type="search" placeholder="Search source language" autocomplete="off" />
          <select id="sourceLang"></select>
        </label>
        <button id="swapLanguages" class="swap-button" type="button" title="Swap languages">⇄</button>
        <label>
          <span>To</span>
          <input id="targetSearch" type="search" placeholder="Search target language" autocomplete="off" />
          <select id="targetLang"></select>
        </label>
      </section>

      <section class="panels">
        <label class="panel">
          <span>Source text</span>
          <textarea id="sourceText" rows="14" placeholder="Enter text to translate"></textarea>
        </label>
        <label class="panel">
          <span>Translation</span>
          <textarea id="resultText" rows="14" readonly placeholder="Translation appears here"></textarea>
        </label>
      </section>

      <section class="actions" aria-label="Translation actions">
        <button id="translateButton" type="button">Translate</button>
        <button id="copyButton" type="button">Copy result</button>
        <p id="message" role="status" aria-live="polite"></p>
      </section>
    </main>
    <script src="/static/app.js" defer></script>
  </body>
</html>
```

- [ ] **Step 4: Replace CSS with utility workbench styling**

Replace `translate_service/web/static/styles.css` with CSS that includes:

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: #f5f7f8;
  color: #182026;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.workbench {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}

.topbar,
.language-bar,
.actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.topbar {
  justify-content: space-between;
  margin-bottom: 20px;
}

h1 {
  margin: 0 0 4px;
  font-size: 28px;
  line-height: 1.2;
}

.status,
#message {
  margin: 0;
  min-height: 20px;
  color: #53626d;
}

.language-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  margin-bottom: 16px;
}

label {
  display: grid;
  gap: 8px;
  font-weight: 600;
}

input,
select,
textarea,
button {
  font: inherit;
}

input,
select,
textarea {
  width: 100%;
  border: 1px solid #c9d2d9;
  border-radius: 8px;
  background: #ffffff;
  color: #182026;
}

input,
select {
  min-height: 40px;
  padding: 8px 10px;
}

textarea {
  resize: vertical;
  min-height: 260px;
  padding: 12px;
  line-height: 1.5;
}

.panels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  min-width: 0;
}

button {
  min-height: 40px;
  border: 0;
  border-radius: 8px;
  padding: 0 14px;
  background: #1d4f73;
  color: #ffffff;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.icon-button,
.swap-button,
#copyButton {
  background: #2f3f4a;
}

.swap-button {
  width: 44px;
  padding: 0;
  align-self: end;
}

.actions {
  margin-top: 16px;
  flex-wrap: wrap;
}

#message.error {
  color: #a23131;
}

#message.success {
  color: #1f6b43;
}

@media (max-width: 760px) {
  .workbench {
    padding: 16px;
  }

  .language-bar,
  .panels {
    grid-template-columns: 1fr;
  }

  .swap-button {
    width: 100%;
  }
}
```

- [ ] **Step 5: Replace JavaScript with API client logic**

Replace `translate_service/web/static/app.js` with JavaScript that:

```javascript
const state = {
  languages: [],
};

const elements = {
  sourceText: document.querySelector("#sourceText"),
  resultText: document.querySelector("#resultText"),
  sourceSearch: document.querySelector("#sourceSearch"),
  targetSearch: document.querySelector("#targetSearch"),
  sourceLang: document.querySelector("#sourceLang"),
  targetLang: document.querySelector("#targetLang"),
  swapLanguages: document.querySelector("#swapLanguages"),
  translateButton: document.querySelector("#translateButton"),
  copyButton: document.querySelector("#copyButton"),
  refreshHealth: document.querySelector("#refreshHealth"),
  healthStatus: document.querySelector("#healthStatus"),
  message: document.querySelector("#message"),
};

function showMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = type;
}

function languageLabel(language) {
  return `${language.name} (${language.code})`;
}

function filteredLanguages(query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return state.languages;
  }
  return state.languages.filter((language) => {
    return (
      language.code.toLowerCase().includes(normalized) ||
      language.name.toLowerCase().includes(normalized)
    );
  });
}

function renderLanguageOptions(select, query, preferredCode) {
  const current = preferredCode || select.value;
  const languages = filteredLanguages(query);
  select.replaceChildren(
    ...languages.map((language) => {
      const option = document.createElement("option");
      option.value = language.code;
      option.textContent = languageLabel(language);
      return option;
    }),
  );
  if (languages.some((language) => language.code === current)) {
    select.value = current;
  }
}

async function parseApiError(response) {
  try {
    const body = await response.json();
    return body.message || `Request failed with status ${response.status}`;
  } catch (_error) {
    return `Request failed with status ${response.status}`;
  }
}

async function loadLanguages() {
  const response = await fetch("/languages");
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  const body = await response.json();
  state.languages = body.languages;
  renderLanguageOptions(elements.sourceLang, elements.sourceSearch.value, "en");
  renderLanguageOptions(elements.targetLang, elements.targetSearch.value, "zh");
}

async function loadHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error(await parseApiError(response));
    }
    const body = await response.json();
    const model = body.model || "unknown model";
    const ollama = body.ollama && body.ollama.ok ? "Ollama ready" : "Ollama not ready";
    elements.healthStatus.textContent = `${body.status}: ${model} · ${ollama}`;
  } catch (error) {
    elements.healthStatus.textContent = `Service check failed: ${error.message}`;
  }
}

function swapLanguages() {
  const source = elements.sourceLang.value;
  elements.sourceLang.value = elements.targetLang.value;
  elements.targetLang.value = source;
  showMessage("Languages swapped.");
}

async function translateText() {
  const text = elements.sourceText.value.trim();
  if (!text) {
    showMessage("Enter text to translate.", "error");
    elements.sourceText.focus();
    return;
  }

  elements.translateButton.disabled = true;
  showMessage("Translating...");

  try {
    const response = await fetch("/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        source_lang: elements.sourceLang.value,
        target_lang: elements.targetLang.value,
      }),
    });
    if (!response.ok) {
      throw new Error(await parseApiError(response));
    }
    const body = await response.json();
    elements.resultText.value = body.translation;
    showMessage("Translation complete.", "success");
  } catch (error) {
    showMessage(error.message || "Translation failed.", "error");
  } finally {
    elements.translateButton.disabled = false;
  }
}

async function copyResult() {
  const text = elements.resultText.value;
  if (!text) {
    showMessage("No translation to copy.", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    showMessage("Copied translation.", "success");
  } catch (_error) {
    showMessage("Copy failed. Select the translation and copy manually.", "error");
  }
}

function bindEvents() {
  elements.sourceSearch.addEventListener("input", () => {
    renderLanguageOptions(elements.sourceLang, elements.sourceSearch.value);
  });
  elements.targetSearch.addEventListener("input", () => {
    renderLanguageOptions(elements.targetLang, elements.targetSearch.value);
  });
  elements.swapLanguages.addEventListener("click", swapLanguages);
  elements.translateButton.addEventListener("click", translateText);
  elements.copyButton.addEventListener("click", copyResult);
  elements.refreshHealth.addEventListener("click", loadHealth);
}

async function init() {
  bindEvents();
  try {
    await loadLanguages();
  } catch (error) {
    showMessage(`Could not load languages: ${error.message}`, "error");
  }
  await loadHealth();
}

document.addEventListener("DOMContentLoaded", init);
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Expected: all API/web tests pass.

- [ ] **Step 7: Run lint**

Run:

```bash
.venv/bin/ruff check .
```

Expected: all checks pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add translate_service/web/static tests/test_api.py
git commit -m "feat: add browser translation workbench"
```

---

### Task 3: Document Web UI and Verify End-to-End

**Files:**
- Modify: `README.md`
- Test: `tests/test_api.py`

- [ ] **Step 1: Add README test**

Add this test to `tests/test_api.py`:

```python
def test_readme_documents_local_web_ui():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "Local Web UI" in readme
    assert "http://127.0.0.1:8000/" in readme
    assert "translate serve" in readme
```

Also add this import at the top of `tests/test_api.py`:

```python
from pathlib import Path
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_api.py::test_readme_documents_local_web_ui -q
```

Expected: fails until README is updated.

- [ ] **Step 3: Update README**

Add a concise section near usage instructions:

~~~markdown
## Local Web UI

Start the HTTP service:

```bash
translate serve
```

Then open:

```text
http://127.0.0.1:8000/
```

The browser workbench uses the same local API endpoints as other clients: `/translate`, `/languages`, and `/health`.
~~~

If the README already has a macOS install section, also mention that the `--install-service` LaunchAgent serves the same URL.

- [ ] **Step 4: Run focused README/API tests**

Run:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run full regression**

Run:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
bash -n scripts/install_macos.sh
bash -n scripts/uninstall_macos.sh
```

Expected:

- pytest reports all tests passing.
- ruff reports all checks passed.
- both shell syntax checks exit 0.

- [ ] **Step 6: Start local server smoke**

Run the service:

```bash
.venv/bin/translate serve
```

In another terminal or background session, verify:

```bash
curl -fsS http://127.0.0.1:8000/ | rg "Local Translate"
curl -fsS http://127.0.0.1:8000/static/app.js | rg "translateText"
curl -fsS http://127.0.0.1:8000/health
```

Expected: root HTML and static JavaScript are served, and `/health` returns JSON. If Ollama is unavailable in the environment, record the health JSON rather than treating that as a Web UI failure.

- [ ] **Step 7: Commit**

Run:

```bash
git add README.md tests/test_api.py
git commit -m "docs: document local web UI"
```

---

## Self-Review

- Spec coverage:
  - `GET /` and static assets: Task 1.
  - Browser calls existing API: Task 2.
  - Text input, selectors with filtering, swap, translate, copy, health, errors: Task 2.
  - No frontend build system: Task 1 and Task 2 use plain static files.
  - Deployment docs and smoke: Task 3.
- Placeholder scan:
  - No TBD/TODO placeholders are present.
  - Each task includes exact paths, code, commands, and expected outcomes.
- Type/name consistency:
  - HTML IDs match JavaScript selectors and test assertions.
  - API endpoints match existing route names.
