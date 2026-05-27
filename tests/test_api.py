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
