import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "chrome_extension"


def read_manifest():
    return json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_v3_contract():
    manifest = read_manifest()

    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "Local Translate"
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["action"]["default_popup"] == "popup.html"
    assert manifest["options_page"] == "options.html"


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
        "icons/icon16.svg",
        "icons/icon32.svg",
        "icons/icon48.svg",
        "icons/icon128.svg",
    ]

    for relative_path in expected_files:
        assert (EXTENSION_DIR / relative_path).is_file(), relative_path


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
