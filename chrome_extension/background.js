const NATIVE_HELPER_NAME = "com.local.translate.helper";
const DEFAULT_IDLE_TIMEOUT_MINUTES = 15;
const DEFAULT_STOP_OLLAMA_POLICY = "if-started-by-helper";

const DEFAULT_SETTINGS = {
  serviceUrl: "http://127.0.0.1:8000",
  sourceLang: "en",
  targetLang: "zh",
  idleTimeoutMinutes: DEFAULT_IDLE_TIMEOUT_MINUTES,
  stopOllamaPolicy: DEFAULT_STOP_OLLAMA_POLICY,
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

function isNetworkFailure(error) {
  return error instanceof TypeError || /Failed to fetch|NetworkError/i.test(error?.message || "");
}

function runtimeErrorMessage() {
  return chrome.runtime.lastError?.message || "";
}

function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(NATIVE_HELPER_NAME, message, (response) => {
      const error = runtimeErrorMessage();

      if (error) {
        reject(new Error("Local service is not running and the Chrome helper is not installed."));
        return;
      }

      if (!response || response.ok === false) {
        reject(new Error(response?.error || "Chrome helper could not start the local service."));
        return;
      }

      resolve(response);
    });
  });
}

function idleTimeoutSeconds(settings) {
  const configuredMinutes = settings.idleTimeoutMinutes ?? DEFAULT_IDLE_TIMEOUT_MINUTES;
  const idleTimeoutMinutes =
    configuredMinutes === "" ? DEFAULT_IDLE_TIMEOUT_MINUTES : configuredMinutes;

  return Math.max(0, Number(idleTimeoutMinutes)) * 60;
}

async function ensureReadyWithHelper(settings) {
  return sendNativeMessage({
    type: "ensure_ready",
    service_url: settings.serviceUrl,
    idle_timeout_seconds: idleTimeoutSeconds(settings),
    stop_ollama_policy: settings.stopOllamaPolicy || DEFAULT_STOP_OLLAMA_POLICY,
  });
}

async function requestJson(path, options = {}, retryAfterHelper = true) {
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

    if (retryAfterHelper && isNetworkFailure(error)) {
      await ensureReadyWithHelper(settings);
      return requestJson(path, options, false);
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

  if (message?.type === "LOCAL_TRANSLATE_TEST_HELPER") {
    sendNativeMessage({ type: "ping" })
      .then((result) => sendResponse({ ok: true, result }))
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
