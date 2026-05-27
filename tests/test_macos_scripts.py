import subprocess
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


def test_install_script_verifies_launchagent_after_kickstart():
    script = read_script(INSTALL_SCRIPT)

    kickstart = "launchctl kickstart -k gui/$UID/com.local.translate-service"
    verification = 'launchctl print "gui/$UID/$LABEL" >/dev/null'

    assert verification in script
    assert "Failed to verify LaunchAgent" in script
    assert "launchctl print gui/$UID/$LABEL" in script
    assert "logs in $LOG_DIR" in script
    assert script.index(kickstart) < script.index(verification)


def test_install_script_checks_ollama_http_api_before_model_pull():
    script = read_script(INSTALL_SCRIPT)

    readiness_check = 'curl -fsS "$OLLAMA_BASE_URL/api/tags"'
    model_pull = 'ollama pull "$MODEL"'

    assert readiness_check in script
    assert "start Ollama first" in script
    assert script.index(readiness_check) < script.index(model_pull)


def test_install_script_polls_readiness_and_starts_fresh_local_ollama():
    script = read_script(INSTALL_SCRIPT)

    assert "wait_for_ollama()" in script
    assert "OLLAMA_READY_TIMEOUT_SECONDS=30" in script
    assert 'while [ "$elapsed" -lt "$OLLAMA_READY_TIMEOUT_SECONDS" ]' in script
    assert "brew services start ollama" in script
    assert "ollama serve" in script
    assert "ollama.log" in script
    assert '[ "$OLLAMA_BASE_URL" = "$DEFAULT_OLLAMA_BASE_URL" ]' in script
    assert "Installed Ollama is not ready" in script


def test_install_ollama_starts_existing_local_ollama_after_readiness_failure():
    script = read_script(INSTALL_SCRIPT)

    readiness_failure_branch = 'if ! wait_for_ollama; then'
    install_ollama_guard = '[ "$INSTALL_OLLAMA" -eq 1 ]'
    local_url_guard = '[ "$OLLAMA_BASE_URL" = "$DEFAULT_OLLAMA_BASE_URL" ]'
    start_attempt = "start_local_ollama"
    final_failure = "Ollama HTTP API is not reachable"

    assert readiness_failure_branch in script
    assert install_ollama_guard in script
    assert local_url_guard in script
    assert script.index(readiness_failure_branch) < script.rindex(start_attempt)
    assert script.rindex(start_attempt) < script.index(final_failure)


def test_install_script_validates_port_is_numeric_before_launchagent():
    script = read_script(INSTALL_SCRIPT)

    validation = 'validate_port "$PORT"'
    plist_generation = '"$VENV_DIR/bin/python" - "$PLIST_PATH"'

    assert "validate_port()" in script
    assert 'case "$port" in' in script
    assert '*[!0-9]*' in script
    assert validation in script
    assert script.index(validation) < script.index(plist_generation)


def test_install_script_validates_port_range():
    script = read_script(INSTALL_SCRIPT)

    assert "port < 1 || port > 65535" in script
    assert "--port must be between 1 and 65535." in script


def test_install_script_generates_plist_with_plistlib_not_xml_heredoc():
    script = read_script(INSTALL_SCRIPT)

    assert "import plistlib" in script
    assert "plistlib.dump" in script
    assert "Label" in script
    assert "ProgramArguments" in script
    assert "WorkingDirectory" in script
    assert "EnvironmentVariables" in script
    assert "RunAtLoad" in script
    assert "KeepAlive" in script
    assert "StandardOutPath" in script
    assert "StandardErrorPath" in script
    assert "<plist version=" not in script
    assert "<!DOCTYPE plist" not in script


def test_install_script_backs_up_env_and_rejects_newlines():
    script = read_script(INSTALL_SCRIPT)

    assert 'ENV_PATH="$PROJECT_ROOT/.env"' in script
    assert "ENV_BACKUP_PATH=" in script
    assert "date +%Y%m%d%H%M%S" in script
    assert 'cp "$ENV_PATH" "$ENV_BACKUP_PATH"' in script
    assert "Backed up existing .env to" in script
    assert "literal newlines" in script


def test_install_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
