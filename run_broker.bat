@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo        Starting LifeLane MQTT Broker
echo ========================================================

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
)

"%PY_CMD%" -m scripts.run_broker %*
pause
endlocal
