# LifeLane Windows Desktop Application Software Guide

This guide describes how to run, build, package, and deploy LifeLane on Windows 10 and Windows 11 as a native Windows desktop software application.

---

## 1. Quick Start (One-Click Launch)

If Python 3.10+ is already installed on your Windows machine:

1. Double-click **`run_windows.bat`** in the project root folder.
2. The script will automatically launch the LifeLane Windows Desktop simulator.

If dependencies are not yet installed, run:
```cmd
scripts\install_windows.bat
```
This will create a Python virtual environment (`.venv`), install all requirements (PySide6, Paho MQTT, PyYAML, python-dotenv, PyInstaller), copy `.env.example` to `.env`, and prepare the application.

---

## 2. Running via Command Line / PowerShell

### Using Command Prompt (CMD)
```cmd
REM Install dependencies
scripts\install_windows.bat

REM Run application
run_windows.bat
```

### Using PowerShell
```powershell
# Set execution policy if restricted (one time)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Install dependencies and setup virtual environment
.\scripts\install_windows.ps1

# Run the Windows application
.\scripts\run_windows.ps1
```

### Direct Python Command
```cmd
python -m windows_app.main
```

---

## 3. Building Standalone Windows Software Executable (`LifeLane.exe`)

You can compile LifeLane into a standalone Windows desktop software executable that runs on any compatible 64-bit Windows PC without requiring Python installed:

### One-Step Build Command
Run from Command Prompt:
```cmd
scripts\build_windows_exe.bat
```
Or from PowerShell:
```powershell
.\scripts\build_windows_exe.ps1
```

### Build Artifacts
When the build completes, the standalone Windows software will be in:
```text
dist\LifeLane\
  ├── LifeLane.exe           <-- Double-click to run
  ├── config\
  │    └── junction.yaml
  ├── raspberry_pi_app\
  │    └── resources\icons\
  └── ... Qt6 / Python runtime libraries
```
You can create a desktop shortcut to `dist\LifeLane\LifeLane.exe` or distribute the `dist\LifeLane` folder directly.

---

## 4. Setting Up Mosquitto MQTT Broker on Windows

To connect an Android phone or test live mobile GPS packets over your local Wi-Fi network:

### Step 1: Install Mosquitto
You can install Eclipse Mosquitto on Windows via Windows Package Manager:
```cmd
winget install EclipseFoundation.Mosquitto
```
Or download the official 64-bit Windows installer from [mosquitto.org/download](https://mosquitto.org/download/).

### Step 2: Configure Mosquitto for LAN Access
Open `C:\Program Files\mosquitto\mosquitto.conf` (in an administrator text editor) or create a custom config file:
```text
listener 1883 0.0.0.0
allow_anonymous true
```

### Step 3: Start Mosquitto Service
Start the service from an Administrator Command Prompt:
```cmd
net start mosquitto
```
Or run directly in a terminal:
```cmd
"C:\Program Files\mosquitto\mosquitto.exe" -v -c "C:\Program Files\mosquitto\mosquitto.conf"
```

### Step 4: Allow Port 1883 in Windows Defender Firewall
To allow incoming MQTT connections from your Android phone on the same Wi-Fi network, run from an Administrator PowerShell:
```powershell
New-NetFirewallRule -DisplayName "LifeLane Mosquitto MQTT" -Direction Inbound -LocalPort 1883 -Protocol TCP -Action Allow
```

---

## 5. Connecting Android Phone to the Windows App

1. Connect both your Windows PC and your Android phone to the **same Wi-Fi network** (or phone hotspot).
2. On your Windows PC, open Command Prompt and run `ipconfig` to find your IPv4 Address (e.g. `192.168.1.50`).
3. In `android_app/local.properties`, configure:
   ```properties
   lifelane.mqtt.host=192.168.1.50
   lifelane.mqtt.port=1883
   ```
4. Build and install the Android app, start an emergency trip, and select **Live mobile GPS** in the Windows application.

---

## 6. Running Tests & Offscreen Verification

To run unit and integration tests:
```powershell
python -m pytest -q
```

To run an offscreen headless smoke test with automatic screenshot capture:
```powershell
python -m windows_app.main --headless-smoke-test --screenshot docs/windows-smoke-test.png
```

---

## 7. Windows Specific Features

- **AppUserModelID**: Automatically sets `LifeLane.Simulator.TrafficPreemption.1.0` so the application groups cleanly and displays its custom icon in the Windows Taskbar.
- **Custom Application Icon**: Native `.ico` multi-resolution icon (from 16x16 to 256x256) embedded in the executable and title bar.
- **Path Resolution**: Handles Windows path separators, PyInstaller frozen temporary directories (`sys._MEIPASS`), and local data directories (`data/lifelane.db`, `logs/lifelane.log`).
- **High-DPI Support**: Native Qt6 DPI scaling on 4K and multi-monitor Windows setups.
