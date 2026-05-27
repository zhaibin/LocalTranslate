from typer.testing import CliRunner

from translate_service.cli import app

runner = CliRunner()


def test_languages_command_lists_languages():
    result = runner.invoke(app, ["languages"])

    assert result.exit_code == 0
    assert "zh-Hans" in result.stdout


def test_text_command_requires_text():
    result = runner.invoke(app, ["text", "--from", "en", "--to", "zh", ""])

    assert result.exit_code != 0
