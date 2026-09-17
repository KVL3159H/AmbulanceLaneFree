@echo off
title LifeLane Web Dashboard
echo.
echo  LifeLane Web Application Simulator
echo  ====================================
echo.

cd /d "%~dp0"

REM Try .venv first
if exist ".venv\Scripts\python.exe" (
    set PYTHON=".venv\Scripts\python.exe"
) else (
    set PYTHON=python
)

echo  Starting server on http://localhost:5000
echo  Press Ctrl+C to stop.
echo.

%PYTHON% -m web_app.server %*
pause
