@echo off
setlocal
cd /d "%~dp0"

REM Check for virtual environment or system python
set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
)

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    if not exist ".venv\Scripts\python.exe" (
        echo ========================================================
        echo [ERROR] Python is not found in your PATH or in .venv.
        echo Please run scripts\install_windows.bat first.
        echo ========================================================
        pause
        exit /b 1
    )
)

REM Launch LifeLane Hub with any supplied arguments
"%PY_CMD%" -m scripts.lifelane_hub %*

endlocal
