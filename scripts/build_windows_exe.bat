@echo off
setlocal
cd /d "%~dp0\.."

echo ========================================================
echo        Building LifeLane Standalone Windows Executable
echo ========================================================

REM Find Python or PyInstaller
set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
)

echo Using %PY_CMD%...

REM Check if pyinstaller is available
%PY_CMD% -c "import PyInstaller" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing PyInstaller into environment...
    %PY_CMD% -m pip install "pyinstaller>=6.0"
)

echo Cleaning previous builds...
if exist "build\LifeLane" rmdir /s /q "build\LifeLane"
if exist "dist\LifeLane" rmdir /s /q "dist\LifeLane"

echo Running PyInstaller...
%PY_CMD% -m PyInstaller --noconfirm lifelane_windows.spec

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed. Inspect the output above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================================
echo [SUCCESS] Windows executable created successfully!
echo Location: %CD%\dist\LifeLane\LifeLane.exe
echo.
echo You can run the application directly by opening:
echo   dist\LifeLane\LifeLane.exe
echo ========================================================
echo.
pause
endlocal
