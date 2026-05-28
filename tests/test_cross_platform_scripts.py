import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"
INSTALL_LINUX_SCRIPT = ROOT / "scripts" / "install_linux.sh"
UNINSTALL_LINUX_SCRIPT = ROOT / "scripts" / "uninstall_linux.sh"
BOOTSTRAP_SCRIPT = ROOT / "scripts" / "install.sh"
INSTALL_WINDOWS_SCRIPT = ROOT / "scripts" / "install_windows.ps1"
UNINSTALL_WINDOWS_SCRIPT = ROOT / "scripts" / "uninstall_windows.ps1"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def project_dependencies() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["dependencies"]


def test_project_pins_cryptography_to_windows_arm_wheel_version():
    assert "cryptography==46.0.3" in project_dependencies()


def test_linux_scripts_exist_and_are_executable():
    assert INSTALL_LINUX_SCRIPT.exists()
    assert INSTALL_LINUX_SCRIPT.stat().st_mode & 0o111
    assert UNINSTALL_LINUX_SCRIPT.exists()
    assert UNINSTALL_LINUX_SCRIPT.stat().st_mode & 0o111


def test_linux_install_script_exposes_expected_options():
    script = read(INSTALL_LINUX_SCRIPT)

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


def test_linux_install_script_uses_project_venv_dotenv_and_user_systemd():
    script = read(INSTALL_LINUX_SCRIPT)

    assert '[ "$(uname -s)" = "Linux" ]' in script
    assert 'VENV_DIR="$PROJECT_ROOT/.venv"' in script
    assert '"$PYTHON_BIN" -m venv "$VENV_DIR"' in script
    assert '"$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"' in script
    assert 'ENV_PATH="$PROJECT_ROOT/.env"' in script
    assert 'SERVICE_PATH="$HOME/.config/systemd/user/translate-service.service"' in script
    assert "systemctl --user daemon-reload" in script
    assert "systemctl --user enable --now translate-service.service" in script
    assert "sudo " not in script


def test_linux_install_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_LINUX_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_linux_uninstall_script_removes_user_systemd_service_conservatively():
    script = read(UNINSTALL_LINUX_SCRIPT)

    assert '[ "$(uname -s)" = "Linux" ]' in script
    assert "systemctl --user disable --now translate-service.service" in script
    assert 'rm -f "$SERVICE_PATH"' in script
    assert 'rm -rf "$PROJECT_ROOT/.venv"' in script
    assert "ollama rm" not in script
    assert "sudo" not in script


def test_linux_uninstall_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(UNINSTALL_LINUX_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_github_bootstrap_script_exists_and_is_executable():
    assert BOOTSTRAP_SCRIPT.exists()
    assert BOOTSTRAP_SCRIPT.stat().st_mode & 0o111


def test_github_bootstrap_script_detects_platform_and_deploys_checkout():
    script = read(BOOTSTRAP_SCRIPT)

    assert 'DEFAULT_REPO_URL="https://github.com/zhaibin/LocalTranslate.git"' in script
    assert 'DEFAULT_INSTALL_DIR="${LOCALTRANSLATE_INSTALL_DIR:-$HOME/.local/share/local-translate}"' in script
    assert 'git clone "$REPO_URL" "$INSTALL_DIR"' in script
    assert 'git -C "$INSTALL_DIR" fetch --tags origin "$REF"' in script
    assert 'git -C "$INSTALL_DIR" checkout --detach FETCH_HEAD' in script
    assert "Darwin)" in script
    assert 'PLATFORM_SCRIPT="scripts/install_macos.sh"' in script
    assert "Linux)" in script
    assert 'PLATFORM_SCRIPT="scripts/install_linux.sh"' in script
    assert "MINGW*|MSYS*|CYGWIN*)" in script
    assert 'PLATFORM_SCRIPT="scripts/install_windows.ps1"' in script


def test_github_bootstrap_defaults_to_ollama_model_and_service_install():
    script = read(BOOTSTRAP_SCRIPT)

    assert "INSTALL_OLLAMA=1" in script
    assert "INSTALL_SERVICE=1" in script
    assert "PULL_MODEL=1" in script
    assert "--no-install-ollama" in script
    assert "--no-install-service" in script
    assert 'INSTALL_ARGS+=("--install-ollama")' in script
    assert 'INSTALL_ARGS+=("--install-service")' in script
    assert 'INSTALL_ARGS+=("--pull-model")' in script
    assert 'INSTALL_ARGS+=("--no-pull-model")' in script


def test_github_bootstrap_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(BOOTSTRAP_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_windows_scripts_exist():
    assert INSTALL_WINDOWS_SCRIPT.exists()
    assert UNINSTALL_WINDOWS_SCRIPT.exists()


def test_windows_install_script_exposes_expected_parameters():
    script = read(INSTALL_WINDOWS_SCRIPT)

    for expected in [
        "[switch]$InstallService",
        "[switch]$InstallOllama",
        "[switch]$NoPullModel",
        "[string]$HostName",
        "[int]$Port",
        "[string]$Model",
        "[string]$SourceLang",
        "[string]$TargetLang",
        "[string]$OllamaBaseUrl",
    ]:
        assert expected in script


def test_windows_install_script_uses_project_venv_dotenv_and_scheduled_task():
    script = read(INSTALL_WINDOWS_SCRIPT)

    assert "$VenvDir = Join-Path $ProjectRoot '.venv'" in script
    assert "$EnvPath = Join-Path $ProjectRoot '.env'" in script
    assert '"-m", "venv"' in script
    assert '"pip", "install", "-e"' in script
    assert "Register-ScheduledTask" in script
    assert "TranslateService" in script
    assert "New-ScheduledTaskPrincipal" in script
    assert "-LogonType Interactive" in script
    assert "Start-ScheduledTask -TaskName $TaskName" in script


def test_windows_install_script_stops_on_scheduled_task_cmdlet_errors():
    script = read(INSTALL_WINDOWS_SCRIPT)

    assert "Register-ScheduledTask" in script
    assert "Register-ScheduledTask" in script and "-ErrorAction Stop" in script
    assert "Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop" in script
    assert "Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop" in script


def test_windows_install_script_checks_native_command_exit_codes_before_continuing():
    script = read(INSTALL_WINDOWS_SCRIPT)

    assert "function Invoke-CheckedNative" in script
    assert "ValueFromRemainingArguments" not in script
    assert (
        'Invoke-CheckedNative "Install Python package dependencies" $PythonExe '
        '@("-m", "pip", "install", "-e", "$ProjectRoot")'
    ) in script
    assert (
        'Invoke-CheckedNative "Install Ollama" winget '
        '@("install", "--id", "Ollama.Ollama", "--exact"'
    ) in script
    assert script.index('Invoke-CheckedNative "Install Python package dependencies"') < script.index(
        'Write-Step "[5/7] Writing configuration"'
    )


def test_windows_install_script_prefers_python_exe_before_py_launcher():
    script = read(INSTALL_WINDOWS_SCRIPT)

    assert "Get-Command python -ErrorAction SilentlyContinue" in script
    assert "Get-Command py -ErrorAction SilentlyContinue" in script
    assert script.index("Get-Command python -ErrorAction SilentlyContinue") < script.index(
        "Get-Command py -ErrorAction SilentlyContinue"
    )


def test_windows_uninstall_script_removes_scheduled_task_conservatively():
    script = read(UNINSTALL_WINDOWS_SCRIPT)

    assert "[switch]$RemoveVenv" in script
    assert "Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false" in script
    assert "Remove-Item -Recurse -Force $VenvDir" in script
    assert "ollama rm" not in script


def test_readme_documents_linux_and_windows_install_paths():
    readme = read(README)

    for expected in [
        "## GitHub One-Line Install",
        "https://raw.githubusercontent.com/zhaibin/LocalTranslate/main/scripts/install.sh",
        "LOCALTRANSLATE_INSTALL_DIR",
        "## Linux One-Command Install",
        "scripts/install_linux.sh",
        "systemctl --user status translate-service.service",
        "scripts/uninstall_linux.sh",
        "## Windows PowerShell Install",
        "powershell -ExecutionPolicy Bypass -File scripts\\install_windows.ps1",
        "Get-ScheduledTask -TaskName TranslateService",
        "powershell -ExecutionPolicy Bypass -File scripts\\uninstall_windows.ps1",
    ]:
        assert expected in readme
