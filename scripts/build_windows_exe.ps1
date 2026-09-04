# LifeLane Windows Executable Builder PowerShell Script
$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Building LifeLane Standalone Windows Executable" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonCmd = $VenvPython
} else {
    $PythonCmd = "python"
}

Write-Host "Using Python: $PythonCmd" -ForegroundColor Green

# Ensure PyInstaller is installed
& $PythonCmd -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    & $PythonCmd -m pip install "pyinstaller>=6.0"
}

# Clean existing builds
if (Test-Path "build\LifeLane") { Remove-Item -Recurse -Force "build\LifeLane" }
if (Test-Path "dist\LifeLane") { Remove-Item -Recurse -Force "dist\LifeLane" }

Write-Host "Running PyInstaller with lifelane_windows.spec..." -ForegroundColor Yellow
& $PythonCmd -m PyInstaller --noconfirm lifelane_windows.spec

if ($LASTEXITCODE -eq 0) {
    $ExePath = Join-Path $ProjectRoot "dist\LifeLane\LifeLane.exe"
    Write-Host "`n========================================================" -ForegroundColor Green
    Write-Host "[SUCCESS] Standalone Windows software executable created!" -ForegroundColor Green
    Write-Host "Executable: $ExePath" -ForegroundColor White
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Error "PyInstaller build failed. Check log output above."
}
