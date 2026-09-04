# LifeLane Windows Runner PowerShell Script
$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       LifeLane Windows Desktop Simulator" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    Write-Host "Using virtual environment: $VenvPython" -ForegroundColor Green
    & $VenvPython -m windows_app.main @args
} else {
    $SysPython = (Get-Command python -ErrorAction SilentlyContinue)
    if ($SysPython) {
        Write-Host "Using system Python: $($SysPython.Source)" -ForegroundColor Green
        & python -m windows_app.main @args
    } else {
        Write-Error "Python was not found on your system. Please run scripts\install_windows.ps1 first."
    }
}
