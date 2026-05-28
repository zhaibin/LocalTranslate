from fastapi.testclient import TestClient

from translate_service.api.app import create_app


class FakeService:
    async def translate(
        self,
        *,
        text: str,
        source_lang: str | None = None,
        target_lang: str | None = None,
    ):
        if text == "boom":
            raise RuntimeError("unexpected")
        return {
            "translation": "你好",
            "source_lang": {"code": source_lang or "en", "name": "English"},
            "target_lang": {"code": target_lang or "zh", "name": "Chinese"},
            "model": "translategemma:latest",
        }

    async def health(self):
        return {"status": "ok", "model": "translategemma:latest", "ollama": {"ok": True}}


def test_translate_route_returns_translation():
    client = TestClient(create_app(FakeService()))

    response = client.post("/translate", json={"text": "Hello", "source_lang": "en", "target_lang": "zh"})

    assert response.status_code == 200
    assert response.json()["translation"] == "你好"


def test_languages_route_returns_supported_languages():
    client = TestClient(create_app(FakeService()))

    response = client.get("/languages")

    assert response.status_code == 200
    assert {"code": "zh-Hans", "name": "Chinese"} in response.json()["languages"]


def test_health_route_returns_status():
    client = TestClient(create_app(FakeService()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_web_root_returns_translation_workbench_html():
    client = TestClient(create_app(FakeService()))

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<main id="app"' in response.text
    assert 'src="/static/app.js"' in response.text
    assert 'href="/static/styles.css"' in response.text
    for expected in [
        'id="sourceText"',
        'id="sourceSearch"',
        'id="sourceLang"',
        'id="targetSearch"',
        'id="targetLang"',
        'id="swapLanguages"',
        'id="translateButton"',
        'id="copyButton"',
        'id="resultText"',
        'id="healthStatus"',
        'id="refreshHealth"',
        'id="message"',
    ]:
        assert expected in response.text


def test_web_static_assets_are_served():
    client = TestClient(create_app(FakeService()))

    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert "application/javascript" in js_response.headers["content-type"]
    assert "async function translateText" in js_response.text
    for expected in [
        "loadLanguages",
        "loadHealth",
        "swapLanguages",
        "copyResult",
        "renderLanguageOptions",
        "ensureLanguageOption",
        "renderLanguageOptions(elements.sourceLang",
        "showMessage",
    ]:
        assert expected in js_response.text
    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert ".workbench" in css_response.text
