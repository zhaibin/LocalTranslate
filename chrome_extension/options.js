const DEFAULT_SETTINGS = {
  serviceUrl: "http://127.0.0.1:8000",
  sourceLang: "en",
  targetLang: "zh",
};

const FALLBACK_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "zh", name: "Chinese" },
];

let settings = { ...DEFAULT_SETTINGS };

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
  const rawUrl = String(value || "").trim().replace(/\/+$/, "");
  const url = new URL(rawUrl);

  if (url.protocol !== "http:") {
    throw new Error("Service URL must use http.");
  }

  if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
    throw new Error("Service URL must point to 127.0.0.1 or localhost.");
  }

  return url.toString().replace(/\/+$/, "");
}

function toLanguageList(result) {
  if (Array.isArray(result)) {
    return result;
  }

  if (Array.isArray(result?.languages)) {
    return result.languages;
  }

  return FALLBACK_LANGUAGES;
}

function renderLanguages(languages) {
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

  if (!elements.sourceLang.value) {
    elements.sourceLang.value = DEFAULT_SETTINGS.sourceLang;
  }

  if (!elements.targetLang.value) {
    elements.targetLang.value = DEFAULT_SETTINGS.targetLang;
  }
}

async function fetchJson(serviceUrl, path) {
  const response = await fetch(`${serviceUrl}${path}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}.`);
  }

  return response.json();
}

async function loadSettings() {
  const stored = await chrome.storage.local.get(DEFAULT_SETTINGS);
  settings = {
    ...DEFAULT_SETTINGS,
    ...stored,
  };
  elements.serviceUrl.value = settings.serviceUrl;
}

async function loadLanguages() {
  const serviceUrl = validateServiceUrl(elements.serviceUrl.value || settings.serviceUrl);
  const body = await fetchJson(serviceUrl, "/languages");
  renderLanguages(toLanguageList(body));
}

function renderFallbackLanguages() {
  renderLanguages(FALLBACK_LANGUAGES);
}

async function saveSettings() {
  try {
    const serviceUrl = validateServiceUrl(elements.serviceUrl.value);
    settings = {
      serviceUrl,
      sourceLang: elements.sourceLang.value,
      targetLang: elements.targetLang.value,
    };

    await chrome.storage.local.set(settings);
    elements.serviceUrl.value = serviceUrl;
    setMessage("Options saved.", "success");
  } catch (error) {
    setMessage(error.message || "Options could not be saved.", "error");
  }
}

async function resetSettings() {
  settings = { ...DEFAULT_SETTINGS };
  await chrome.storage.local.set(settings);
  elements.serviceUrl.value = settings.serviceUrl;

  try {
    await loadLanguages();
    setMessage("Options reset.", "success");
  } catch (error) {
    renderFallbackLanguages();
    setMessage(`Options reset. Could not load languages: ${error.message}`, "error");
  }
}

function getHealthMessage(body) {
  const status = body?.status || (body?.ok ? "ok" : "unknown");
  const model = body?.model || body?.ollama?.model || "unknown model";

  return `Service ${status}: ${model}`;
}

async function testConnection() {
  try {
    const serviceUrl = validateServiceUrl(elements.serviceUrl.value);
    const body = await fetchJson(serviceUrl, "/health");
    setMessage(getHealthMessage(body), "success");
  } catch (error) {
    setMessage(`Connection failed: ${error.message}`, "error");
  }
}

async function reloadLanguages() {
  try {
    await loadLanguages();
    setMessage("Languages reloaded.", "success");
  } catch (error) {
    renderFallbackLanguages();
    setMessage(`Could not reload languages: ${error.message}`, "error");
  }
}

async function init() {
  elements.saveButton.addEventListener("click", saveSettings);
  elements.resetButton.addEventListener("click", resetSettings);
  elements.testButton.addEventListener("click", testConnection);
  elements.reloadLanguagesButton.addEventListener("click", reloadLanguages);

  await loadSettings();

  try {
    await loadLanguages();
  } catch (error) {
    renderFallbackLanguages();
    setMessage(`Could not load languages: ${error.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  init();
});
