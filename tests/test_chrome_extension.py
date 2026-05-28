import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "chrome_extension"


def read_manifest():
    return json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))


def read_readme_section(heading):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    marker = f"## {heading}"
    start = readme.index(marker)
    end = readme.find("\n## ", start + len(marker))

    if end == -1:
        return readme[start:]

    return readme[start:end]


def test_manifest_v3_contract():
    manifest = read_manifest()

    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "Local Translate"
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["action"]["default_popup"] == "popup.html"
    assert manifest["options_page"] == "options.html"
    assert manifest["icons"] == {
        "16": "icons/icon16.png",
        "32": "icons/icon32.png",
        "48": "icons/icon48.png",
        "128": "icons/icon128.png",
    }


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
        "icons/icon16.png",
        "icons/icon32.png",
        "icons/icon48.png",
        "icons/icon128.png",
    ]

    for relative_path in expected_files:
        assert (EXTENSION_DIR / relative_path).is_file(), relative_path


def test_readme_documents_chrome_extension_usage():
    section = read_readme_section("Chrome Extension")

    assert "Chrome Extension" in section
    assert "chrome_extension/" in section
    assert "Load unpacked" in section
    assert "http://127.0.0.1:8000" in section
    assert "does not save" in section
    assert "translation history" in section


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
    assert "AbortController" in background
    assert "Local translation timed out after" in background
    assert "Try shorter text or check Ollama." in background
    assert "getErrorServiceUrl" in background
