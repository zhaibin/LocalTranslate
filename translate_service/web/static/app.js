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

function ensureLanguageOption(languages, code) {
  if (!code || languages.some((language) => language.code === code)) {
    return languages;
  }
  const language = state.languages.find((candidate) => candidate.code === code);
  if (!language) {
    return languages;
  }
  return [language, ...languages];
}

function renderLanguageOptions(select, query, preferredCode) {
  const current = preferredCode || select.value;
  const languages = ensureLanguageOption(filteredLanguages(query), current);
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
    elements.healthStatus.textContent = `${body.status}: ${model} - ${ollama}`;
  } catch (error) {
    elements.healthStatus.textContent = `Service check failed: ${error.message}`;
  }
}

function swapLanguages() {
  const source = elements.sourceLang.value;
  const target = elements.targetLang.value;
  renderLanguageOptions(elements.sourceLang, elements.sourceSearch.value, target);
  renderLanguageOptions(elements.targetLang, elements.targetSearch.value, source);
  elements.sourceLang.value = target;
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
