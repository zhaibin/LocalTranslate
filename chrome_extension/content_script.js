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
      width: min(380px, calc(100vw - 40px));
      max-height: min(440px, calc(100vh - 40px));
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
    #${OVERLAY_ID},
    #${OVERLAY_ID} * {
      box-sizing: border-box;
    }
    #${OVERLAY_ID} .lt-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    #${OVERLAY_ID} .lt-title {
      font-size: 15px;
      font-weight: 700;
    }
    #${OVERLAY_ID} .lt-body {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    #${OVERLAY_ID} .lt-muted {
      color: #57606a;
    }
    #${OVERLAY_ID} .lt-error {
      color: #b42318;
    }
    #${OVERLAY_ID} .lt-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 12px;
    }
    #${OVERLAY_ID} .lt-status {
      flex: 1;
      min-height: 20px;
      color: #57606a;
      font-size: 13px;
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
    #${OVERLAY_ID} button:hover {
      background: #eef1f4;
    }
  `;
  document.documentElement.appendChild(style);
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

async function copyText(text, statusNode) {
  try {
    await navigator.clipboard.writeText(text);
    statusNode.textContent = "Copied.";
  } catch (_error) {
    statusNode.textContent = "Copy failed. Select the text and copy manually.";
  }
}

function renderOverlay(payload = {}) {
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
  title.className = "lt-title";
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
  status.className = "lt-status";

  if (payload.status === "loading") {
    body.classList.add("lt-muted");
    body.textContent = "Translating...";
  } else if (payload.status === "success") {
    const text = getTranslationText(payload);
    body.textContent = text || "No translation text was returned.";

    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy";
    copy.disabled = !text;
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
    message?.type === "LOCAL_TRANSLATE_LOADING" ||
    message?.type === "LOCAL_TRANSLATE_RESULT"
  ) {
    renderOverlay(message.payload || {});
  }
});
