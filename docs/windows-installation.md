# LifeLane Windows Desktop Application Software Guide

This guide describes how to run, build, package, and deploy LifeLane on Windows 10 and Windows 11 as a native Windows desktop software application.

---

## 1. Quick Start (Unified Control Hub & One-Click Launch)

If Python 3.10+ is installed on your Windows machine:

1. Double-click **`run.bat`** (or **`lifelane.bat`**) in the project root to open the interactive **LifeLane Control Hub**.
2. From the menu, you can instantly:
   - **[1] Launch Desktop Simulator (PySide6 GUI)**
   - **[2] Start Built-in Zero-Dependency MQTT Broker**
   - **[3] Launch All-In-One Full Stack (Broker + Simulator)**
   - **[4] Build Android APK**
   - **[5] Build & Install APK to Connected Phone (ADB)**
   - **[6] Build Standalone Windows Executable (.exe)**
   - **[7] Run Automated PyTest Suite**
   - **[8] Run LifeLane Doctor (System Diagnostics)**
   - **[9] Network & MQTT IP Helper**

You can also run direct single-purpose batch files at any time:
- **`run_windows.bat`**: Run desktop simulator immediately.
- **`run_broker.bat`**: Start the pure-Python MQTT broker.
- **`scripts\build_android.bat`**: Compile and install the Android app.
- **`scripts\build_windows_exe.bat`**: Package standalone `LifeLane.exe`.
- **`scripts\install_windows.bat`**: Install all dependencies and set up virtual environment.

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

## 4. MQTT Broker on Windows (Built-in or Mosquitto)

LifeLane now includes a **built-in zero-dependency Pure-Python MQTT 3.1.1 broker** that works immediately without installing Mosquitto:

### Option A: Built-in Pure-Python Broker (Recommended for Development)
Simply run:
```cmd
run_broker.bat
```
or choose **Option [2]** in `run.bat`. It will automatically display your PC's Wi-Fi / LAN IP address for phone connection and handle all LifeLane telemetry.

### Option B: External Eclipse Mosquitto
If you prefer running the native Mosquitto daemon:
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
