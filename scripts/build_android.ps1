<#
.SYNOPSIS
    Builds the LifeLane Android APK and optionally installs it to an attached device.
#>

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       Building LifeLane Android Application (APK)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Check Java
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if (-not $javaCmd) {
    Write-Host "[ERROR] Java JDK was not found in PATH." -ForegroundColor Red
    Write-Host "Please ensure JDK 17 or JDK 21 is installed and available."
    Exit 1
}

# Run Gradle Build
Set-Location "$ProjectRoot\android_app"
$gradlew = if ($IsWindows -or $env:OS -eq "Windows_NT") { ".\gradlew.bat" } else { "./gradlew" }

Write-Host "[1/2] Building Debug APK with Gradle..." -ForegroundColor Yellow
& $gradlew assembleDebug

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Android build failed. Inspect the Gradle output above." -ForegroundColor Red
    Set-Location $ProjectRoot
    Exit $LASTEXITCODE
}

Set-Location $ProjectRoot
$apkPath = "$ProjectRoot\android_app\app\build\outputs\apk\debug\app-debug.apk"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "[SUCCESS] Android APK built successfully!" -ForegroundColor Green
Write-Host "APK Location: $apkPath" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""

# Find ADB
$adb = (Get-Command adb -ErrorAction SilentlyContinue)?.Source
if (-not $adb) {
    $fallbackAdb = Join-Path $env:USERPROFILE "AppData\Local\Android\Sdk\platform-tools\adb.exe"
    if (Test-Path $fallbackAdb) { $adb = $fallbackAdb }
}

if ($adb) {
    Write-Host "Checking for connected Android devices via ADB..." -ForegroundColor Cyan
    $devices = & $adb devices | Where-Object { $_ -match "\tdevice$" }
    if ($devices) {
        Write-Host "[INFO] Detected connected Android device(s):" -ForegroundColor Green
        $devices | ForEach-Object { Write-Host "   -> $_" -ForegroundColor Gray }
        $resp = Read-Host "Would you like to install and launch this APK now? (Y/n)"
        if ($resp -eq "" -or $resp -match "^[Yy]") {
            Write-Host "Installing $apkPath..." -ForegroundColor Yellow
            & $adb install -r $apkPath
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[SUCCESS] APK installed! Launching LifeLane on device..." -ForegroundColor Green
                & $adb shell am start -n org.lifelane.mobile/.MainActivity
            }
        }
    } else {
        Write-Host "[INFO] No active Android device or emulator detected via ADB." -ForegroundColor Gray
        Write-Host "To install on your phone, copy the APK or connect your phone via USB with USB Debugging enabled."
    }
}
