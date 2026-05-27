from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "scripts" / "install_macos.sh"
UNINSTALL_SCRIPT = ROOT / "scripts" / "uninstall_macos.sh"


def read_script(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_install_script_exists_and_is_executable():
    assert INSTALL_SCRIPT.exists()
    assert INSTALL_SCRIPT.stat().st_mode & 0o111


def test_install_script_exposes_expected_options():
    script = read_script(INSTALL_SCRIPT)

    for option in [
        "--install-service",
        "--install-ollama",
        "--pull-model",
        "--no-pull-model",
        "--host",
        "--port",
        "--model",
        "--source-lang",
        "--target-lang",
        "--ollama-base-url",
        "--help",
    ]:
        assert option in script


def test_install_script_uses_project_local_virtualenv_and_editable_install():
    script = read_script(INSTALL_SCRIPT)

    assert 'VENV_DIR="$PROJECT_ROOT/.venv"' in script
    assert '"$PYTHON_BIN" -m venv "$VENV_DIR"' in script
    assert '"$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"' in script


def test_install_script_writes_env_and_launchagent_paths():
    script = read_script(INSTALL_SCRIPT)

    assert "OLLAMA_MODEL=" in script
    assert "DEFAULT_SOURCE_LANG=" in script
    assert "DEFAULT_TARGET_LANG=" in script
    assert "com.local.translate-service.plist" in script
    assert "Library/LaunchAgents" in script
    assert "Library/Logs/translate-service" in script


def test_install_script_uses_user_launchagent_not_system_daemon():
    script = read_script(INSTALL_SCRIPT)

    assert "launchctl bootstrap gui/$UID" in script
    assert "launchctl kickstart -k gui/$UID/com.local.translate-service" in script
    assert "/Library/LaunchDaemons" not in script
    assert "sudo " not in script
