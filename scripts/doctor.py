"""LifeLane System Doctor & Environment Diagnostics Tool.

This utility inspects and validates the entire development & runtime environment:
- Python version & PySide6 runtime
- Java JDK (17/21) & Android SDK Platform / Build Tools
- ADB connectivity & connected Android devices
- MQTT Broker port 1883 & local IPv4 LAN network configuration
- Project configuration files (.env, junction.yaml, local.properties)
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Enable ANSI colors on Windows console
os.system("")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def check_mark(status: bool) -> str:
    return f"{GREEN}[PASS]{RESET}" if status else f"{RED}[FAIL]{RESET}"


def warn_mark() -> str:
    return f"{YELLOW}[WARN]{RESET}"


def info_mark() -> str:
    return f"{CYAN}[INFO]{RESET}"


def print_header(title: str):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


def run_command(cmd: List[str], timeout: float = 5.0) -> Tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            shell=(os.name == "nt"),
        )
        return proc.returncode, proc.stdout.strip()
    except Exception as e:
        return -1, str(e)


def check_python_environment(project_root: Path) -> bool:
    print_header("1. Python & Desktop Runtime")
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    py_ok = (py_ver.major == 3 and py_ver.minor >= 10)
    print(f" {check_mark(py_ok)} Python Version: {py_str} (Target: >= 3.10)")

    # Virtual Environment
    in_venv = (sys.prefix != sys.base_prefix) or (project_root / ".venv").exists()
    venv_path = project_root / ".venv"
    if in_venv:
        print(f" {check_mark(True)} Virtual Environment: Detected ({'.venv' if venv_path.exists() else sys.prefix})")
    else:
        print(f" {warn_mark()} Virtual Environment: Not active (run scripts\\install_windows.bat to create .venv)")

    # Key packages
    packages = [
        ("PySide6", "PySide6 (Qt GUI Desktop Shell)"),
        ("paho.mqtt", "paho-mqtt (MQTT Protocol Client)"),
        ("yaml", "PyYAML (Junction Configuration)"),
        ("dotenv", "python-dotenv (Environment Variables)"),
        ("pytest", "pytest (Automated Test Runner)"),
        ("pytestqt", "pytest-qt (Qt UI Testing Plugin)"),
        ("PyInstaller", "PyInstaller (Standalone EXE Packaging)"),
    ]

    all_pkg_ok = True
    for mod_name, label in packages:
        try:
            mod = __import__(mod_name)
            ver = getattr(mod, "__version__", "Installed")
            print(f" {check_mark(True)} {label}: {ver}")
        except ImportError:
            all_pkg_ok = False
            print(f" {check_mark(False)} {label}: Missing")

    return py_ok and all_pkg_ok


def check_java_environment() -> bool:
    print_header("2. Java JDK Environment (for Android Build)")
    code, out = run_command(["java", "-version"])
    if code != 0:
        print(f" {check_mark(False)} Java JDK: Not found in PATH. Please install JDK 17 or 21.")
        return False

    first_line = out.splitlines()[0] if out else "Unknown"
    # Extract version
    match = re.search(r'version "([^"]+)"', first_line)
    ver_str = match.group(1) if match else first_line
    print(f" {check_mark(True)} Java JDK: {ver_str}")

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        print(f" {info_mark()} JAVA_HOME: {java_home}")
    return True


def check_android_environment(project_root: Path) -> Tuple[bool, Optional[Path]]:
    print_header("3. Android SDK & Mobile Build Environment")
    local_prop = project_root / "android_app" / "local.properties"
    sdk_dir_path: Optional[Path] = None

    if local_prop.exists():
        try:
            with open(local_prop, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("sdk.dir="):
                        val = line.split("=", 1)[1].strip()
                        sdk_dir_path = Path(val.replace("\\", "/"))
                        break
        except Exception:
            pass

    if not sdk_dir_path or not sdk_dir_path.exists():
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if android_home:
            sdk_dir_path = Path(android_home)
        else:
            default_sdk = Path.home() / "AppData" / "Local" / "Android" / "Sdk"
            if default_sdk.exists():
                sdk_dir_path = default_sdk

    if sdk_dir_path and sdk_dir_path.exists():
        print(f" {check_mark(True)} Android SDK Directory: {sdk_dir_path}")

        # Check platforms
        platforms_dir = sdk_dir_path / "platforms"
        platforms = [p.name for p in platforms_dir.iterdir() if p.is_dir()] if platforms_dir.exists() else []
        has_36 = any("android-36" in p for p in platforms)
        if has_36:
            print(f" {check_mark(True)} Target SDK Platform: android-36 (Installed: {', '.join(platforms)})")
        else:
            print(f" {warn_mark()} Target SDK Platform android-36 not found (Installed: {', '.join(platforms) if platforms else 'None'})")

        # Check build-tools
        bt_dir = sdk_dir_path / "build-tools"
        bts = [b.name for b in bt_dir.iterdir() if b.is_dir()] if bt_dir.exists() else []
        print(f" {check_mark(len(bts) > 0)} Android Build Tools: {', '.join(bts) if bts else 'None'}")

        # Check gradlew
        gw = project_root / "android_app" / ("gradlew.bat" if os.name == "nt" else "gradlew")
        print(f" {check_mark(gw.exists())} Gradle Wrapper: {gw.name} ({'Ready' if gw.exists() else 'Missing'})")
        return True, sdk_dir_path
    else:
        print(f" {check_mark(False)} Android SDK: Not detected. Please configure android_app/local.properties")
        return False, None


def check_adb_and_devices(sdk_path: Optional[Path]):
    print_header("4. ADB Connectivity & Connected Mobile Devices")
    adb_path = shutil.which("adb")
    if not adb_path and sdk_path:
        candidate = sdk_path / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if candidate.exists():
            adb_path = str(candidate)

    if not adb_path:
        print(f" {warn_mark()} ADB Tool: Not found in PATH or SDK platform-tools.")
        return

    print(f" {check_mark(True)} ADB Tool: {adb_path}")
    code, out = run_command([adb_path, "devices", "-l"])
    if code == 0:
        lines = [
            l.strip()
            for l in out.splitlines()
            if l.strip() and not l.strip().startswith("*") and not l.strip().startswith("List of")
        ]
        if lines:
            print(f" {GREEN}[FOUND]{RESET} Connected Devices/Emulators ({len(lines)}):")
            for line in lines:
                print(f"    -> {line}")
        else:
            print(f" {info_mark()} No physical Android phone or running emulator currently connected via ADB.")
            print("        Tip: Connect phone via USB with USB Debugging enabled, or start an Android Emulator.")
    else:
        print(f" {warn_mark()} Failed to query ADB devices.")


def check_network_and_mqtt(project_root: Path):
    print_header("5. Network Configuration & MQTT Broker Diagnostics")
    port = 1883

    # Check port 1883
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    res = sock.connect_ex(("127.0.0.1", port))
    sock.close()

    if res == 0:
        print(f" {check_mark(True)} MQTT Port 1883: ACTIVE & LISTENING (Broker is currently running)")
    else:
        print(f" {info_mark()} MQTT Port 1883: Available (Start broker via run_broker.bat or menu)")

    # Enumerate IPs
    ips: List[Tuple[str, str]] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            p_ip = s.getsockname()[0]
            if p_ip:
                ips.append(("Wi-Fi / Primary LAN", p_ip))
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not any(ip == existing[1] for existing in ips):
                ips.append(("Host Interface", ip))
    except Exception:
        pass

    print(f" {info_mark()} Host IP Addresses for Mobile Connectivity:")
    for label, ip in ips:
        print(f"    * {label:22s} : {BOLD}{GREEN}{ip}{RESET}")

    # Check android local.properties MQTT host
    local_prop = project_root / "android_app" / "local.properties"
    if local_prop.exists():
        try:
            with open(local_prop, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r"lifelane\.mqtt\.host=([^\r\n]+)", content)
                if match:
                    configured_ip = match.group(1).strip()
                    print(f" {info_mark()} Android App Configured Host : {configured_ip}")
                    if ips and configured_ip not in [ip for _, ip in ips] and configured_ip != "10.0.2.2":
                        print(f"    {YELLOW}^ Note: For a physical phone, match this to your Wi-Fi IP ({ips[0][1]}){RESET}")
        except Exception:
            pass


def check_project_files(project_root: Path):
    print_header("6. Project Configuration & Assets")
    files_to_check = [
        ("config/junction.yaml", True),
        (".env.example", True),
        (".env", False),
        ("raspberry_pi_app/resources/icons/lifelane.ico", True),
        ("lifelane_windows.spec", True),
    ]

    for rel_path, required in files_to_check:
        p = project_root / rel_path
        if p.exists():
            print(f" {check_mark(True)} {rel_path}")
        else:
            if required:
                print(f" {check_mark(False)} {rel_path} (Missing required file)")
            else:
                print(f" {warn_mark()} {rel_path} (Optional/Generated file not found)")


def main():
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    print("=" * 68)
    print(f"{BOLD}           LIFELANE SYSTEM DOCTOR & DIAGNOSTICS           {RESET}")
    print("=" * 68)
    print(f"Project Directory : {project_root}")
    print(f"Operating System  : {platform.system()} {platform.release()} ({platform.machine()})")

    check_python_environment(project_root)
    check_java_environment()
    sdk_ok, sdk_path = check_android_environment(project_root)
    check_adb_and_devices(sdk_path)
    check_network_and_mqtt(project_root)
    check_project_files(project_root)

    print("\n" + "=" * 68)
    print(f"{BOLD}{GREEN}Diagnostics completed!{RESET}")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
