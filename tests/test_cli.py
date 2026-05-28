from typer.testing import CliRunner

import translate_service.cli as cli
from translate_service.cli import app

runner = CliRunner()


def test_languages_command_lists_languages():
    result = runner.invoke(app, ["languages"])

    assert result.exit_code == 0
    assert "zh-Hans" in result.stdout


def test_cli_output_escapes_characters_not_supported_by_stdout_encoding():
    assert cli._encode_for_stdout("ok 𐍈", "gbk") == "ok \\U00010348"


def test_text_command_requires_text():
    result = runner.invoke(app, ["text", "--from", "en", "--to", "zh", ""])

    assert result.exit_code != 0


def test_text_command_prints_translation_and_forwards_languages(monkeypatch):
    calls = []

    class FakeService:
        async def translate(
            self,
            *,
            text: str,
            source_lang: str | None = None,
            target_lang: str | None = None,
        ):
            calls.append(
                {
                    "text": text,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                }
            )
            return {"translation": "你好"}

    monkeypatch.setattr(cli, "_service", lambda: FakeService())

    result = runner.invoke(app, ["text", "--from", "en", "--to", "zh", "Hello"])

    assert result.exit_code == 0
    assert result.stdout == "你好\n"
    assert calls == [{"text": "Hello", "source_lang": "en", "target_lang": "zh"}]
