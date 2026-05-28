const DEFAULT_SETTINGS = {
  serviceUrl: "http://127.0.0.1:8000",
  sourceLang: "en",
  targetLang: "zh",
};

const CONTEXT_MENU_ID = "local-translate-selection";
const SESSION_RESULT_KEY = "latestContextMenuResult";
const REQUEST_TIMEOUT_MS = 25000;
const REQUEST_TIMEOUT_SECONDS = REQUEST_TIMEOUT_MS / 1000;

function normalizeServiceUrl(serviceUrl) {
  const rawUrl = String(serviceUrl || "").trim().replace(/\/+$/, "");
  const url = new URL(rawUrl);

  if (url.protocol !== "http:") {
    throw new Error("Service URL must use http.");
  }

  if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
    throw new Error("Service URL must point to 127.0.0.1 or localhost.");
  }

  return url.toString().replace(/\/+$/, "");
}

async function getSettings() {
  const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);

  return {
    ...DEFAULT_SETTINGS,
    ...settings,
    serviceUrl: normalizeServiceUrl(settings.serviceUrl || DEFAULT_SETTINGS.serviceUrl),
  };
}

async function parseApiError(response) {
  try {
    const data = await response.json();
    return data.message || data.error || data.detail || response.statusText;
  } catch (_error) {
    return response.statusText || "Request failed.";
  }
}

async function requestJson(path, options = {}) {
  const settings = await getSettings();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${settings.serviceUrl}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      const message = await parseApiError(response);
      throw new Error(message || `Request failed with status ${response.status}.`);
    }

    return response.json();
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        `Local translation timed out after ${REQUEST_TIMEOUT_SECONDS} seconds. Try shorter text or check Ollama.`,
      );
    }

    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function translateText(text, sourceLang, targetLang) {
  const sourceText = String(text || "").trim();

  if (!sourceText) {
    throw new Error("Select text to translate.");
  }

  return requestJson("/translate", {
    method: "POST",
    body: JSON.stringify({
      text: sourceText,
      source_lang: sourceLang,
      target_lang: targetLang,
    }),
  });
}

async function sendToTab(tabId, message) {
  try {
    return await chrome.tabs.sendMessage(tabId, message);
  } catch (_error) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content_script.js"],
    });

    return chrome.tabs.sendMessage(tabId, message);
  }
}

async function openFallback(payload) {
  await chrome.storage.session.set({ [SESSION_RESULT_KEY]: payload });
  await chrome.tabs.create({
    url: chrome.runtime.getURL("result.html"),
  });
}

async function showResult(tabId, payload) {
  try {
    await sendToTab(tabId, {
      type: "LOCAL_TRANSLATE_RESULT",
      payload,
    });
  } catch (_error) {
    await openFallback(payload);
  }
}

function getErrorServiceUrl(settings) {
  try {
    return normalizeServiceUrl(settings?.serviceUrl || DEFAULT_SETTINGS.serviceUrl);
  } catch (_error) {
    return DEFAULT_SETTINGS.serviceUrl;
  }
}

async function handleContextMenuClick(info, tab) {
  if (!tab?.id) {
    return;
  }

  const sourceText = String(info.selectionText || "").trim();
  let settings = { ...DEFAULT_SETTINGS };

  try {
    settings = await getSettings();

    try {
      await sendToTab(tab.id, {
        type: "LOCAL_TRANSLATE_LOADING",
        payload: {
          status: "loading",
          sourceText,
          serviceUrl: settings.serviceUrl,
        },
      });
    } catch (_error) {
      // The fallback result page will still show the final result or error.
    }

    const result = await translateText(sourceText, settings.sourceLang, settings.targetLang);

    await showResult(tab.id, {
      status: "success",
      sourceText,
      translatedText: result.translated_text || result.translation || result.text || "",
      sourceLang: settings.sourceLang,
      targetLang: settings.targetLang,
      serviceUrl: settings.serviceUrl,
      raw: result,
    });
  } catch (error) {
    await showResult(tab.id, {
      status: "error",
      sourceText,
      error: error.message || "Translation failed.",
      serviceUrl: getErrorServiceUrl(settings),
    });
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
  if (message?.type === "LOCAL_TRANSLATE_GET_SETTINGS") {
    getSettings()
      .then((settings) => sendResponse({ ok: true, settings }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message?.type === "LOCAL_TRANSLATE_TRANSLATE") {
    getSettings()
      .then((settings) => {
        const sourceLang = message.sourceLang || settings.sourceLang;
        const targetLang = message.targetLang || settings.targetLang;
        return translateText(message.text, sourceLang, targetLang);
      })
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message?.type === "LOCAL_TRANSLATE_LANGUAGES") {
    requestJson("/languages")
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message?.type === "LOCAL_TRANSLATE_HEALTH") {
    requestJson("/health")
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  return false;
});
