@echo off
setlocal
cd /d "%~dp0\.."

echo ========================================================
echo        LifeLane Windows Setup and Dependency Installer
echo ========================================================

REM Check Python availability
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please download and install Python 3.10 or newer from https://www.python.org/
    echo Be sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Checking Python environment...
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment at .venv...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [2/4] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo [3/4] Installing dependencies from requirements.txt and PyInstaller...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.0" "Pillow"

echo [4/4] Setting up .env file...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env"
        echo Created default .env from .env.example
    )
)

echo.
echo ========================================================
echo Installation completed successfully!
echo You can now run LifeLane using:
echo   run_windows.bat
echo Or build a standalone .exe with:
echo   scripts\build_windows_exe.bat
echo ========================================================
echo.
pause
endlocal
