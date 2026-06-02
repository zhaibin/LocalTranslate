const DEFAULT_SETTINGS = {
  serviceUrl: "http://127.0.0.1:8000",
  sourceLang: "en",
  targetLang: "zh",
  idleTimeoutMinutes: 15,
  stopOllamaPolicy: "if-started-by-helper",
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
  idleTimeoutMinutes: document.querySelector("#idleTimeoutMinutes"),
  stopOllamaPolicy: document.querySelector("#stopOllamaPolicy"),
  saveButton: document.querySelector("#saveButton"),
  resetButton: document.querySelector("#resetButton"),
  testButton: document.querySelector("#testButton"),
  testHelperButton: document.querySelector("#testHelperButton"),
  reloadLanguagesButton: document.querySelector("#reloadLanguagesButton"),
  message: document.querySelector("#message"),
  helperStatus: document.querySelector("#helperStatus"),
};

function setMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = `message ${type}`.trim();
}

function setHelperStatus(text, type = "") {
  elements.helperStatus.textContent = text;
  elements.helperStatus.className = `message ${type}`.trim();
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

  if (url.username || url.password) {
    throw new Error("Service URL must not include credentials.");
  }

  if (url.pathname && url.pathname !== "/") {
    throw new Error("Service URL must not include a path.");
  }

  if (url.search || url.hash) {
    throw new Error("Service URL must not include query or fragment.");
  }

  if (!url.port || Number(url.port) < 1) {
    throw new Error("Service URL must include a valid port.");
  }

  return url.toString().replace(/\/+$/, "");
}

function normalizeIdleTimeout(value) {
  const idleTimeoutMinutes =
    value === "" || value === undefined || value === null
      ? DEFAULT_SETTINGS.idleTimeoutMinutes
      : Number.parseInt(value, 10);

  if (!Number.isFinite(idleTimeoutMinutes) || idleTimeoutMinutes < 0) {
    throw new Error("Idle timeout must be zero or greater.");
  }

  return idleTimeoutMinutes;
}

function normalizeStopPolicy(value) {
  const allowedPolicies = new Set(["never", "if-started-by-helper", "always"]);

  if (!value) {
    return DEFAULT_SETTINGS.stopOllamaPolicy;
  }

  if (!allowedPolicies.has(value)) {
    throw new Error("Choose a valid Ollama stop policy.");
  }

  return value;
}

function toLanguageList(result) {
  const languages = Array.isArray(result) ? result : result?.languages;

  if (!Array.isArray(languages)) {
    return FALLBACK_LANGUAGES;
  }

  const validLanguages = languages.filter((language) => String(language?.code || "").trim());

  return validLanguages.length > 0 ? validLanguages : FALLBACK_LANGUAGES;
}

function resolveLanguageCode(languages, preferredCode, defaultCode) {
  const codes = new Set(languages.map((language) => language.code));

  if (codes.has(preferredCode)) {
    return preferredCode;
  }

  if (codes.has(defaultCode)) {
    return defaultCode;
  }

  return languages[0].code;
}

function renderLanguages(languages) {
  const languageOptions = toLanguageList(languages);

  for (const select of [elements.sourceLang, elements.targetLang]) {
    select.replaceChildren(
      ...languageOptions.map((language) => {
        const option = document.createElement("option");
        option.value = language.code;
        option.textContent = `${language.name} (${language.code})`;
        return option;
      }),
    );
  }

  elements.sourceLang.value = resolveLanguageCode(
    languageOptions,
    settings.sourceLang,
    DEFAULT_SETTINGS.sourceLang,
  );
  elements.targetLang.value = resolveLanguageCode(
    languageOptions,
    settings.targetLang,
    DEFAULT_SETTINGS.targetLang,
  );
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

function sendMessage(message) {
  return chrome.runtime.sendMessage(message);
}

async function loadSettings() {
  const stored = await chrome.storage.local.get(DEFAULT_SETTINGS);
  settings = {
    ...DEFAULT_SETTINGS,
    ...stored,
  };
  elements.serviceUrl.value = settings.serviceUrl;
  elements.idleTimeoutMinutes.value = normalizeIdleTimeout(settings.idleTimeoutMinutes);
  elements.stopOllamaPolicy.value = normalizeStopPolicy(settings.stopOllamaPolicy);
}

async function loadLanguages() {
  const serviceUrl = validateServiceUrl(elements.serviceUrl.value || settings.serviceUrl);
  const body = await fetchJson(serviceUrl, "/languages");
  renderLanguages(body);
}

function renderFallbackLanguages() {
  renderLanguages(FALLBACK_LANGUAGES);
}

async function saveSettings() {
  try {
    const serviceUrl = validateServiceUrl(elements.serviceUrl.value);
    const idleTimeoutMinutes = normalizeIdleTimeout(elements.idleTimeoutMinutes.value);
    const stopOllamaPolicy = normalizeStopPolicy(elements.stopOllamaPolicy.value);
    settings = {
      serviceUrl,
      sourceLang: elements.sourceLang.value,
      targetLang: elements.targetLang.value,
      idleTimeoutMinutes,
      stopOllamaPolicy,
    };

    await chrome.storage.local.set(settings);
    elements.serviceUrl.value = serviceUrl;
    elements.idleTimeoutMinutes.value = idleTimeoutMinutes;
    elements.stopOllamaPolicy.value = stopOllamaPolicy;
    setMessage("Options saved.", "success");
  } catch (error) {
    setMessage(error.message || "Options could not be saved.", "error");
  }
}

async function resetSettings() {
  settings = { ...DEFAULT_SETTINGS };
  await chrome.storage.local.set(settings);
  elements.serviceUrl.value = settings.serviceUrl;
  elements.idleTimeoutMinutes.value = settings.idleTimeoutMinutes;
  elements.stopOllamaPolicy.value = settings.stopOllamaPolicy;

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

async function testHelper() {
  try {
    const response = await sendMessage({ type: "LOCAL_TRANSLATE_TEST_HELPER" });

    if (!response?.ok) {
      throw new Error(response?.error || "Chrome helper did not respond.");
    }

    setHelperStatus("Chrome helper is available.", "success");
  } catch (error) {
    setHelperStatus(`Chrome helper check failed: ${error.message}`, "error");
  }
}

async function init() {
  elements.saveButton.addEventListener("click", saveSettings);
  elements.resetButton.addEventListener("click", resetSettings);
  elements.testButton.addEventListener("click", testConnection);
  elements.testHelperButton.addEventListener("click", testHelper);
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
