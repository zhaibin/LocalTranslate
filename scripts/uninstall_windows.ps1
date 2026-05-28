param(
    [switch]$RemoveVenv
)

$ErrorActionPreference = "Stop"
$TaskName = "TranslateService"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot ".venv"

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
    throw "Error: This uninstaller only supports Windows."
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task $TaskName"
} else {
    Write-Host "No scheduled task named $TaskName was found."
}

if ($RemoveVenv) {
    if (Test-Path $VenvDir) {
        Remove-Item -Recurse -Force $VenvDir
        Write-Host "Removed $VenvDir"
    }
} else {
    Write-Host "Kept project .venv. Rerun with -RemoveVenv to remove it."
}

Write-Host "Uninstall complete."
Write-Host "Kept project source, Ollama, and Ollama models."
