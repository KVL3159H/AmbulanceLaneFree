# LifeLane Windows Setup & Dependency Installer
$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "     LifeLane Windows Setup and Installer (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$SysPython = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $SysPython) {
    Write-Error "Python 3.10+ is required. Please install Python and ensure it is in your PATH."
    exit 1
}

$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/4] Creating virtual environment at .venv..." -ForegroundColor Yellow
    python -m venv $VenvDir
} else {
    Write-Host "[1/4] Virtual environment already exists at .venv." -ForegroundColor Green
}

Write-Host "[2/4] Upgrading pip..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip

Write-Host "[3/4] Installing dependencies from requirements.txt & PyInstaller..." -ForegroundColor Yellow
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m pip install "pyinstaller>=6.0" "Pillow"

Write-Host "[4/4] Setting up .env configuration..." -ForegroundColor Yellow
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "Created .env from .env.example" -ForegroundColor Green
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "Installation completed successfully!" -ForegroundColor Green
Write-Host "Run the application with: .\scripts\run_windows.ps1 or run_windows.bat" -ForegroundColor White
Write-Host "Build standalone exe with: .\scripts\build_windows_exe.ps1" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
