@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo        LifeLane Windows Desktop Simulator
echo ========================================================

REM Find Python executable: prefer .venv, then system python
set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    echo.
    echo [ERROR] Python was not found in your PATH and .venv was not found.
    echo Please run scripts\install_windows.bat first or install Python 3.10+.
    echo.
    pause
    exit /b 1
)

echo [INFO] Starting desktop simulator...
"%PY_CMD%" -m raspberry_pi_app.main %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    pause
)

endlocal
