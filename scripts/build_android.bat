@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo ========================================================
echo        Building LifeLane Android Application (APK)
echo ========================================================

REM Verify Java JDK
where java >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Java JDK was not found in your PATH.
    echo Please ensure JDK 17 or JDK 21 is installed and added to your PATH.
    pause
    exit /b 1
)

cd android_app
if not exist "gradlew.bat" (
    echo [ERROR] gradlew.bat was not found in android_app directory.
    pause
    exit /b 1
)

echo [1/2] Building Debug APK with Gradle...
call gradlew.bat assembleDebug
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Android build failed. Inspect the Gradle output above.
    cd ..
    pause
    exit /b %ERRORLEVEL%
)

cd ..
set "APK_PATH=android_app\app\build\outputs\apk\debug\app-debug.apk"

echo.
echo ========================================================
echo [SUCCESS] Android APK built successfully!
echo APK Location: %CD%\%APK_PATH%
echo ========================================================
echo.

REM Check for ADB and connected devices
set "ADB_CMD=adb"
where adb >nul 2>nul
if %ERRORLEVEL% neq 0 (
    if exist "%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe" (
        set "ADB_CMD=%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    )
)

"%ADB_CMD%" version >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo Checking for connected Android devices via ADB...
    "%ADB_CMD%" devices | findstr /R /C:"[0-9a-zA-Z]	device$" >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        echo [INFO] Detected connected Android device/emulator.
        set /p "INSTALL_NOW=Would you like to install and launch this APK now? (Y/N, default Y): "
        if "!INSTALL_NOW!"=="" set "INSTALL_NOW=Y"
        if /i "!INSTALL_NOW!"=="Y" (
            echo Installing %APK_PATH%...
            "%ADB_CMD%" install -r "%APK_PATH%"
            if !ERRORLEVEL! equ 0 (
                echo [SUCCESS] APK installed! Launching LifeLane on device...
                "%ADB_CMD%" shell am start -n org.lifelane.mobile/.MainActivity
            ) else (
                echo [WARN] Failed to install APK to device.
            )
        )
    ) else (
        echo [INFO] No active Android device or emulator detected via ADB.
        echo To install on your phone, copy the APK file or connect your phone via USB with USB Debugging enabled.
    )
)

echo.
pause
endlocal
