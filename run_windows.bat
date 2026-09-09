@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo        LifeLane Windows Desktop Simulator
echo ========================================================

REM Check if virtual environment exists
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment (.venv)...
    ".venv\Scripts\python.exe" -m windows_app.main %*
    goto :end
)

REM Fallback to system python
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Using system Python...
    python -m windows_app.main %*
    goto :end
)

echo.
echo [ERROR] Python was not found in your PATH and .venv was not found.
echo Please run scripts\install_windows.bat first or install Python 3.10+.
echo.
pause

:end
endlocal
