@echo off
cd /d "%~dp0"
if not exist "dist\connected-prototype\LifeLane\LifeLane.exe" (
    echo Connected prototype executable is missing. See docs\connected-prototype.md.
    pause
    exit /b 1
)
start "LifeLane" "dist\connected-prototype\LifeLane\LifeLane.exe"
