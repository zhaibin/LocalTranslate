from translate_service.config import Settings


def test_settings_defaults():
    settings = Settings()

    assert str(settings.ollama_base_url) == "http://127.0.0.1:11434/"
    assert settings.ollama_model == "translategemma:latest"
    assert settings.default_source_lang == "en"
    assert settings.default_target_lang == "zh"
    assert settings.request_timeout_seconds == 120


def test_settings_can_be_overridden():
    settings = Settings(
        ollama_base_url="http://localhost:9999",
        ollama_model="custom:latest",
        default_source_lang="ja",
        default_target_lang="en",
        request_timeout_seconds=30,
    )

    assert str(settings.ollama_base_url) == "http://localhost:9999/"
    assert settings.ollama_model == "custom:latest"
    assert settings.default_source_lang == "ja"
    assert settings.default_target_lang == "en"
    assert settings.request_timeout_seconds == 30
