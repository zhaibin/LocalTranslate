const SESSION_RESULT_KEY = "latestContextMenuResult";
const DEFAULT_SERVICE_URL = "http://127.0.0.1:8000";

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

function getTranslationText(payload) {
  return (
    payload.translatedText ||
    payload.translation?.translation ||
    payload.raw?.translation ||
    payload.raw?.translated_text ||
    payload.raw?.text ||
    ""
  );
}

function getResultText(payload) {
  if (payload.status === "success") {
    return getTranslationText(payload);
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
  elements.resultText.textContent = getResultText(payload);

  if (payload.status === "success" && !getTranslationText(payload)) {
    elements.copyButton.disabled = true;
    setMessage("No translation text was returned.", "error");
    return;
  }

  if (payload.status === "error") {
    const serviceUrl = payload.serviceUrl || DEFAULT_SERVICE_URL;
    elements.copyButton.disabled = true;
    setMessage(`Check the local service: ${serviceUrl}`, "error");
  }
}

elements.copyButton.addEventListener("click", copyResult);
elements.closeButton.addEventListener("click", () => window.close());
document.addEventListener("DOMContentLoaded", init);
