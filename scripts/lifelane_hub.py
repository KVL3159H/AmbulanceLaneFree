"""LifeLane Unified Control Hub & CLI.

Provides an interactive dashboard and one-click unified orchestrator for:
- Desktop Simulator (Windows & Pi)
- Zero-Dependency Pure-Python MQTT Broker
- Combined Full-Stack Launcher (Broker + Simulator)
- Android App Compilation & ADB Auto-Installation
- Standalone Windows .exe Packaging
- Automated PyTest Test Suite
- System Doctor & Environment Diagnostics
- LAN IP & Android Config Sync
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# Enable ANSI on Windows
os.system("")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_python_exe() -> str:
    """Find the best Python executable (virtualenv preferred)."""
    venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def get_local_ip() -> str:
    """Get the primary local LAN IP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def is_port_in_use(port: int = 1883) -> bool:
    """Check if a port is currently listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    res = sock.connect_ex(("127.0.0.1", port))
    sock.close()
    return res == 0


def action_run_desktop():
    print(f"\n{BOLD}{CYAN}>>> Launching LifeLane Desktop Simulator...{RESET}\n")
    py = get_python_exe()
    cmd = [py, "-m", "windows_app.main"]
    subprocess.run(cmd, cwd=PROJECT_ROOT)


def action_run_web():
    print(f"\n{BOLD}{CYAN}>>> Launching LifeLane Web Application (http://localhost:5000)...{RESET}\n")
    py = get_python_exe()
    cmd = [py, "-m", "web_app.server"]
    subprocess.run(cmd, cwd=PROJECT_ROOT)


def action_run_broker():
    print(f"\n{BOLD}{CYAN}>>> Starting LifeLane MQTT Broker...{RESET}\n")
    py = get_python_exe()
    cmd = [py, "-m", "scripts.run_broker"]
    subprocess.run(cmd, cwd=PROJECT_ROOT)


def action_run_fullstack():
    print(f"\n{BOLD}{CYAN}>>> Launching LifeLane Full-Stack (Broker + Simulator)...{RESET}\n")
    py = get_python_exe()

    # If broker is not running, start it in a separate process/window
    if not is_port_in_use(1883):
        print(f"{GREEN}[INFO]{RESET} Starting background MQTT Broker on port 1883...")
        if os.name == "nt":
            # Launch in separate console window on Windows
            subprocess.Popen(
                ["start", "cmd", "/c", py, "-m", "scripts.run_broker"],
                shell=True,
                cwd=PROJECT_ROOT,
            )
        else:
            subprocess.Popen([py, "-m", "scripts.run_broker"], cwd=PROJECT_ROOT)
        time.sleep(1.2)
    else:
        print(f"{GREEN}[INFO]{RESET} MQTT Broker is already active on port 1883.")

    # Now launch the desktop application
    action_run_desktop()


def action_build_android(install: bool = False):
    print(f"\n{BOLD}{CYAN}>>> Building Android Application...{RESET}\n")
    android_dir = PROJECT_ROOT / "android_app"
    gradlew = "gradlew.bat" if os.name == "nt" else "./gradlew"

    res = subprocess.run([str(android_dir / gradlew), "assembleDebug"], cwd=android_dir)
    if res.returncode != 0:
        print(f"\n{RED}[ERROR] Android build failed.{RESET}")
        return

    apk_path = android_dir / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    print(f"\n{BOLD}{GREEN}[SUCCESS] APK generated at:{RESET}\n{apk_path}\n")

    if install:
        action_install_android(apk_path)


def action_install_android(apk_path: Optional[Path] = None):
    if not apk_path:
        apk_path = PROJECT_ROOT / "android_app" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"

    if not apk_path.exists():
        print(f"{YELLOW}[INFO]{RESET} APK not found. Building debug APK first...")
        action_build_android(install=False)

    print(f"{BOLD}{CYAN}>>> Checking for connected ADB devices...{RESET}")
    # Locate ADB
    adb_cmd = "adb"
    default_adb = Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    if default_adb.exists():
        adb_cmd = str(default_adb)

    try:
        proc = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True)
        lines = [l for l in proc.stdout.splitlines()[1:] if "\tdevice" in l]
        if not lines:
            print(f"{YELLOW}[WARN]{RESET} No Android device or emulator currently connected via ADB.")
            print(f"       Connect your physical phone via USB (with USB Debugging) or start an Emulator.")
            return

        print(f"{GREEN}[FOUND]{RESET} Connected device: {lines[0].split()[0]}")
        print(f"Installing APK ({apk_path.name})...")
        install_res = subprocess.run([adb_cmd, "install", "-r", str(apk_path)])
        if install_res.returncode == 0:
            print(f"{BOLD}{GREEN}[SUCCESS] Installed successfully! Launching LifeLane...{RESET}")
            subprocess.run([adb_cmd, "shell", "am", "start", "-n", "org.lifelane.mobile/.MainActivity"])
        else:
            print(f"{RED}[ERROR] Installation failed.{RESET}")
    except Exception as e:
        print(f"{RED}[ERROR] Could not execute ADB: {e}{RESET}")


def action_build_exe():
    print(f"\n{BOLD}{CYAN}>>> Building LifeLane Standalone Windows Executable (.exe)...{RESET}\n")
    py = get_python_exe()

    # Ensure pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print(f"{YELLOW}[INFO] Installing PyInstaller...{RESET}")
        subprocess.run([py, "-m", "pip", "install", "pyinstaller>=6.0", "Pillow"], cwd=PROJECT_ROOT)

    cmd = [py, "-m", "PyInstaller", "--noconfirm", "lifelane_windows.spec"]
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode == 0:
        exe_path = PROJECT_ROOT / "dist" / "LifeLane" / "LifeLane.exe"
        print(f"\n{BOLD}{GREEN}[SUCCESS] Executable built successfully!{RESET}")
        print(f"Executable Location: {exe_path}\n")
    else:
        print(f"\n{RED}[ERROR] PyInstaller build failed.{RESET}")


def action_run_tests():
    print(f"\n{BOLD}{CYAN}>>> Running Automated PyTest Suite...{RESET}\n")
    py = get_python_exe()
    subprocess.run([py, "-m", "pytest", "-v"], cwd=PROJECT_ROOT)


def action_run_doctor():
    py = get_python_exe()
    subprocess.run([py, "-m", "scripts.doctor"], cwd=PROJECT_ROOT)


def action_configure_network():
    print(f"\n{BOLD}{CYAN}=== Network & Android MQTT Configuration Helper ==={RESET}")
    lan_ip = get_local_ip()
    local_prop = PROJECT_ROOT / "android_app" / "local.properties"

    current_host = "Not Configured"
    if local_prop.exists():
        try:
            with open(local_prop, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("lifelane.mqtt.host="):
                        current_host = line.strip().split("=", 1)[1]
        except Exception:
            pass

    print(f" Detected PC LAN Wi-Fi IP  : {BOLD}{GREEN}{lan_ip}{RESET}")
    print(f" Current Android MQTT Host : {BOLD}{YELLOW}{current_host}{RESET}")
    print("-" * 55)
    print(" 1) Set Android App host to PC Wi-Fi IP (for physical phone testing)")
    print(" 2) Set Android App host to 10.0.2.2 (for Android Studio emulator)")
    print(" 3) Set Android App host to custom IP")
    print(" 0) Back")

    choice = input("\nSelect an option [0-3]: ").strip()
    new_ip = None
    if choice == "1":
        new_ip = lan_ip
    elif choice == "2":
        new_ip = "10.0.2.2"
    elif choice == "3":
        new_ip = input("Enter custom IP or hostname: ").strip()

    if new_ip:
        # Update local.properties
        lines = []
        if local_prop.exists():
            with open(local_prop, "r", encoding="utf-8") as f:
                lines = f.readlines()

        has_host = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("lifelane.mqtt.host="):
                new_lines.append(f"lifelane.mqtt.host={new_ip}\n")
                has_host = True
            else:
                new_lines.append(line)

        if not has_host:
            new_lines.append(f"lifelane.mqtt.host={new_ip}\n")

        with open(local_prop, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print(f"\n{BOLD}{GREEN}[SUCCESS] Updated android_app/local.properties with host = {new_ip}{RESET}\n")


def print_banner():
    broker_running = is_port_in_use(1883)
    broker_status = f"{GREEN}ONLINE (Port 1883){RESET}" if broker_running else f"{YELLOW}OFFLINE{RESET}"
    lan_ip = get_local_ip()

    print(rf"""{CYAN}{BOLD}
  _      _  __     _                        
 | |    (_)/ _|   | |                       
 | |     _| |_ ___| |     __ _ _ __   ___   
 | |    | |  _/ _ \ |    / _` | '_ \ / _ \  
 | |____| | |  __/ |___| (_| | | | |  __/  
 |______|_|_| \___|______\__,_|_| |_|\___|  
{RESET}{BOLD}   Smart Ambulance Signal Preemption Simulator · v1.2{RESET}
{CYAN}==================================================================={RESET}
 Local Wi-Fi / LAN IP : {BOLD}{GREEN}{lan_ip}{RESET}
 MQTT Broker Status   : {broker_status}
 Python Environment   : {sys.version.split()[0]} ({'Venv' if (PROJECT_ROOT / '.venv').exists() else 'System'})
{CYAN}==================================================================={RESET}
""")


def interactive_menu():
    while True:
        print_banner()
        print(f" {BOLD}[1]{RESET}  Launch Desktop Simulator (PySide6 GUI)")
        print(f" {BOLD}[2]{RESET}  Start Local MQTT Broker (Zero-Dependency)")
        print(f" {BOLD}[3]{RESET}  Launch All-In-One Full Stack (Broker + Simulator)")
        print(f" {BOLD}[4]{RESET}  Build Android APK (Debug)")
        print(f" {BOLD}[5]{RESET}  Build & Install Android App to Connected Phone (ADB)")
        print(f" {BOLD}[6]{RESET}  Build Standalone Windows Executable (.exe)")
        print(f" {BOLD}[7]{RESET}  Run Automated Test Suite (PyTest 41 Tests)")
        print(f" {BOLD}[8]{RESET}  Run LifeLane Doctor (System Diagnostics)")
        print(f" {BOLD}[9]{RESET}  Network & Android MQTT Config Helper")
        print(f" {BOLD}[0]{RESET}  Exit")
        print(f"{CYAN}-------------------------------------------------------------------{RESET}")

        try:
            choice = input(f"{BOLD}Enter selection [0-9]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting LifeLane Hub.")
            break

        if choice == "1":
            action_run_desktop()
        elif choice == "2":
            action_run_broker()
        elif choice == "3":
            action_run_fullstack()
        elif choice == "4":
            action_build_android(install=False)
        elif choice == "5":
            action_build_android(install=True)
        elif choice == "6":
            action_build_exe()
        elif choice == "7":
            action_run_tests()
        elif choice == "8":
            action_run_doctor()
        elif choice == "9":
            action_configure_network()
        elif choice == "0":
            print("\nGoodbye!")
            break
        else:
            print(f"\n{RED}Invalid selection. Please choose 0 to 9.{RESET}")

        input(f"\n{CYAN}Press Enter to return to menu...{RESET}")
        print("\n" * 2)


def main():
    parser = argparse.ArgumentParser(
        description="LifeLane Smart Ambulance Unified Control Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run directly")

    subparsers.add_parser("desktop", help="Launch the Desktop GUI Simulator")
    subparsers.add_parser("broker", help="Start the pure-Python MQTT Broker")
    subparsers.add_parser("full", help="Start Broker and launch Desktop Simulator")
    subparsers.add_parser("android", help="Build Android APK")
    subparsers.add_parser("install-android", help="Build and install APK via ADB")
    subparsers.add_parser("build-exe", help="Build standalone Windows .exe")
    subparsers.add_parser("test", help="Run pytest automated test suite")
    subparsers.add_parser("doctor", help="Run system diagnostics")
    subparsers.add_parser("config-ip", help="Configure network IP settings")

    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)

    if args.command == "desktop":
        action_run_desktop()
    elif args.command == "broker":
        action_run_broker()
    elif args.command == "full":
        action_run_fullstack()
    elif args.command == "android":
        action_build_android(install=False)
    elif args.command == "install-android":
        action_install_android()
    elif args.command == "build-exe":
        action_build_exe()
    elif args.command == "test":
        action_run_tests()
    elif args.command == "doctor":
        action_run_doctor()
    elif args.command == "config-ip":
        action_configure_network()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
