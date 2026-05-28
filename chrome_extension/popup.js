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
  sourceText: document.querySelector("#sourceText"),
  sourceLang: document.querySelector("#sourceLang"),
  targetLang: document.querySelector("#targetLang"),
  swapButton: document.querySelector("#swapButton"),
  translateButton: document.querySelector("#translateButton"),
  resultText: document.querySelector("#resultText"),
  copyButton: document.querySelector("#copyButton"),
  optionsButton: document.querySelector("#optionsButton"),
  message: document.querySelector("#message"),
};

function setMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = `message ${type}`.trim();
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

async function loadSettings() {
  const stored = await chrome.storage.local.get(DEFAULT_SETTINGS);
  settings = { ...DEFAULT_SETTINGS, ...stored };
}

async function loadLanguages() {
  const response = await chrome.runtime.sendMessage({ type: "LOCAL_TRANSLATE_LANGUAGES" });

  if (!response?.ok) {
    renderLanguages(FALLBACK_LANGUAGES);
    throw new Error(response?.error || "Could not load languages.");
  }

  renderLanguages(toLanguageList(response.result));
}

function setTranslateLoading(isLoading) {
  elements.translateButton.disabled = isLoading;
  elements.translateButton.textContent = isLoading ? "Translating..." : "Translate";
}

async function translate() {
  const text = elements.sourceText.value.trim();

  if (!text) {
    setMessage("Enter text to translate.", "error");
    return;
  }

  setTranslateLoading(true);
  setMessage("Translating...");

  try {
    const response = await chrome.runtime.sendMessage({
      type: "LOCAL_TRANSLATE_TRANSLATE",
      text,
      sourceLang: elements.sourceLang.value,
      targetLang: elements.targetLang.value,
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Translation failed.");
    }

    const translation = response.result?.translation || "";
    elements.resultText.value = translation;

    if (!translation) {
      setMessage("No translation text was returned.", "error");
      return;
    }

    setMessage("Translation complete.", "success");
  } catch (error) {
    setMessage(error.message || "Translation failed.", "error");
  } finally {
    setTranslateLoading(false);
  }
}

async function copyResult() {
  const text = elements.resultText.value;

  if (!text) {
    setMessage("No translation to copy.", "error");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setMessage("Copied.", "success");
  } catch (_error) {
    setMessage("Copy failed. Select the translation and copy manually.", "error");
  }
}

function swapLanguages() {
  const sourceLang = elements.sourceLang.value;
  elements.sourceLang.value = elements.targetLang.value;
  elements.targetLang.value = sourceLang;
}

async function init() {
  elements.translateButton.addEventListener("click", translate);
  elements.copyButton.addEventListener("click", copyResult);
  elements.swapButton.addEventListener("click", swapLanguages);
  elements.optionsButton.addEventListener("click", () => chrome.runtime.openOptionsPage());

  try {
    await loadSettings();
    await loadLanguages();
  } catch (error) {
    setMessage(error.message || "Could not initialize popup.", "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
