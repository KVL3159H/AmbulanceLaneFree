# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
project_root = Path.cwd()

datas = [
    (str(project_root / "config" / "junction.yaml"), "config"),
    (str(project_root / "raspberry_pi_app" / "resources" / "icons" / "*"), "raspberry_pi_app/resources/icons"),
]

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "paho.mqtt",
    "paho.mqtt.client",
    "paho.mqtt.enums",
    "yaml",
    "dotenv",
    "sqlite3",
    "raspberry_pi_app.core.config",
    "raspberry_pi_app.core.models",
    "raspberry_pi_app.core.signal_states",
    "raspberry_pi_app.core.gps_engine",
    "raspberry_pi_app.core.priority_manager",
    "raspberry_pi_app.core.passage_detector",
    "raspberry_pi_app.core.signal_controller",
    "raspberry_pi_app.core.coordinator",
    "raspberry_pi_app.database.connection",
    "raspberry_pi_app.database.repository",
    "raspberry_pi_app.communication.topics",
    "raspberry_pi_app.communication.message_validator",
    "raspberry_pi_app.communication.mqtt_client",
    "raspberry_pi_app.simulator.simulated_paths",
    "raspberry_pi_app.simulator.gps_simulator",
    "raspberry_pi_app.simulator.ambulance_factory",
    "raspberry_pi_app.ui.main_window",
    "raspberry_pi_app.ui.junction_scene",
    "raspberry_pi_app.ui.traffic_signal_item",
    "raspberry_pi_app.ui.ambulance_item",
    "raspberry_pi_app.ui.event_log_panel",
    "raspberry_pi_app.ui.information_panel",
    "raspberry_pi_app.ui.priority_queue_panel",
    "windows_app",
]

a = Analysis(
    ["windows_app/main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "torch", "scipy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LifeLane",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "raspberry_pi_app" / "resources" / "icons" / "lifelane.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LifeLane",
)
