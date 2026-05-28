param(
    [switch]$InstallService,
    [switch]$InstallOllama,
    [switch]$NoPullModel,
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$Model = "translategemma:latest",
    [string]$SourceLang = "en",
    [string]$TargetLang = "zh",
    [string]$OllamaBaseUrl = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
$TaskName = "TranslateService"
$RequestTimeoutSeconds = 120
$OllamaReadyTimeoutSeconds = 30
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot '.venv'
$EnvPath = Join-Path $ProjectRoot '.env'
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$TranslateExe = Join-Path $VenvDir "Scripts\translate.exe"

function Write-Step($Message) {
    Write-Host $Message
}

function Fail($Message) {
    throw "Error: $Message"
}

function Invoke-CheckedNative {
    param(
        [string]$Description,
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "$Description failed with exit code $LASTEXITCODE."
    }
}

function Validate-NoNewline($Name, $Value) {
    if ($Value -match "[`r`n]") {
        Fail "$Name must not contain literal newlines."
    }
}

function Validate-DotenvToken($Name, $Value) {
    Validate-NoNewline $Name $Value
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match "\s|#|'|`"|[$]|[{}]") {
        Fail "$Name must not be empty or contain whitespace, #, quotes, $, {, or }."
    }
}

function Validate-LangCode($Name, $Value) {
    Validate-NoNewline $Name $Value
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -notmatch "^[A-Za-z0-9-]+$") {
        Fail "$Name must contain only BCP47 language-code characters: A-Z, a-z, 0-9, or '-'."
    }
}

function Validate-Port($Value) {
    if ($Value -lt 1 -or $Value -gt 65535) {
        Fail "-Port must be between 1 and 65535."
    }
}

function Test-OllamaReady {
    try {
        Invoke-RestMethod -Uri "$OllamaBaseUrl/api/tags" -TimeoutSec 5 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-Ollama {
    for ($elapsed = 0; $elapsed -lt $OllamaReadyTimeoutSeconds; $elapsed++) {
        if (Test-OllamaReady) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

Write-Step "[1/7] Checking Windows and Python"
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
    Fail "This installer only supports Windows."
}
if (-not (Test-Path (Join-Path $ProjectRoot "pyproject.toml"))) {
    Fail "Run this script from a valid project checkout."
}

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCommand) {
    $Python = "python"
    $PythonArgs = @()
} else {
    $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        Fail "Python 3.11+ is required."
    }
    $Python = "py"
    $PythonArgs = @("-3")
}
Invoke-CheckedNative "Check Python version" $Python ($PythonArgs + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"))

Write-Step "[2/7] Checking Ollama"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    if ($InstallOllama) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Fail "winget is required for -InstallOllama. Install Ollama manually or install winget."
        }
        Invoke-CheckedNative "Install Ollama" winget @("install", "--id", "Ollama.Ollama", "--exact", "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity")
    } else {
        Fail "Ollama is not installed. Install it manually or rerun with -InstallOllama."
    }
}
if (-not (Wait-Ollama)) {
    Fail "Ollama HTTP API is not reachable at $OllamaBaseUrl. Start Ollama first and rerun the installer."
}

Write-Step "[3/7] Creating virtual environment"
Invoke-CheckedNative "Create virtual environment" $Python ($PythonArgs + @("-m", "venv", "$VenvDir"))

Write-Step "[4/7] Installing translate-service"
Invoke-CheckedNative "Upgrade pip" $PythonExe @("-m", "pip", "install", "--upgrade", "pip")
Invoke-CheckedNative "Install Python package dependencies" $PythonExe @("-m", "pip", "install", "-e", "$ProjectRoot")

Write-Step "[5/7] Writing configuration"
Validate-DotenvToken "OLLAMA_BASE_URL" $OllamaBaseUrl
Validate-DotenvToken "OLLAMA_MODEL" $Model
Validate-LangCode "DEFAULT_SOURCE_LANG" $SourceLang
Validate-LangCode "DEFAULT_TARGET_LANG" $TargetLang
Validate-NoNewline "REQUEST_TIMEOUT_SECONDS" "$RequestTimeoutSeconds"
if (Test-Path $EnvPath) {
    $BackupPath = Join-Path $ProjectRoot (".env.backup." + (Get-Date -Format "yyyyMMddHHmmss"))
    Copy-Item $EnvPath $BackupPath
    Write-Step "Backed up existing .env to $BackupPath"
}
@(
    "OLLAMA_BASE_URL=$OllamaBaseUrl"
    "OLLAMA_MODEL=$Model"
    "DEFAULT_SOURCE_LANG=$SourceLang"
    "DEFAULT_TARGET_LANG=$TargetLang"
    "REQUEST_TIMEOUT_SECONDS=$RequestTimeoutSeconds"
) | Set-Content -Path $EnvPath -Encoding UTF8

if (-not $NoPullModel) {
    Write-Step "[6/7] Pulling Ollama model $Model"
    Invoke-CheckedNative "Pull Ollama model" ollama @("pull", "$Model")
} else {
    Write-Step "[6/7] Skipping model pull"
}

if ($InstallService) {
    Write-Step "[7/7] Installing scheduled task"
    Validate-Port $Port
    $Action = New-ScheduledTaskAction -Execute $TranslateExe -Argument "serve --host $HostName --port $Port" -WorkingDirectory $ProjectRoot
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
    $Settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force -ErrorAction Stop | Out-Null
    Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Start-Sleep -Seconds 2
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ($Task.State -eq "Disabled") {
        Fail "Scheduled task was created but is disabled."
    }
} else {
    Write-Step "[7/7] Skipping scheduled task"
}

& $TranslateExe --help | Out-Null
Write-Step "Install complete."
Write-Step "CLI: $TranslateExe text --from en --to zh `"Hello`""
if ($InstallService) {
    Write-Step "HTTP health: curl http://$HostName`:$Port/health"
    Write-Step "Task: Get-ScheduledTask -TaskName TranslateService"
}
