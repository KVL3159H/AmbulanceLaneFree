"""LifeLane Windows desktop application entry point.

Provides native Windows integration including AppUserModelID for taskbar icon
grouping, high-DPI handling, PyInstaller frozen binary support, and window icon setup.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

APP_USER_MODEL_ID = "LifeLane.Simulator.TrafficPreemption.1.0"


def get_base_directories() -> tuple[Path, Path]:
    """Return (bundle_dir, working_dir).

    bundle_dir: where read-only assets (config, icons) reside (supports PyInstaller sys._MEIPASS).
    working_dir: where mutable data (logs, database, .env) reside.
    """
    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        working_dir = Path(sys.executable).parent
    else:
        bundle_dir = Path(__file__).resolve().parents[1]
        working_dir = bundle_dir
    return bundle_dir, working_dir


def parse_args(bundle_dir: Path, working_dir: Path) -> argparse.Namespace:
    candidates = [
        working_dir / "config" / "junction.yaml",
        bundle_dir / "config" / "junction.yaml",
        bundle_dir / "_internal" / "config" / "junction.yaml",
        Path.cwd() / "config" / "junction.yaml",
    ]
    default_config = next((p for p in candidates if p.exists()), candidates[0])
    default_db = working_dir / "data" / "lifelane.db"

    parser = argparse.ArgumentParser(description="LifeLane Windows Desktop Junction Simulator")
    parser.add_argument("--config", type=Path, default=default_config, help="Path to junction YAML config")
    parser.add_argument("--database", type=Path, default=default_db, help="Path to SQLite database")
    parser.add_argument("--headless-smoke-test", action="store_true", help="Run automated offscreen smoke test")
    parser.add_argument("--screenshot", type=Path, help="Save screenshot when smoke test completes")
    return parser.parse_args()


def configure_logging(log_root: Path) -> None:
    log_directory = log_root / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_directory / "lifelane.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handlers: list[logging.Handler] = [handler]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, handlers=handlers)


def set_windows_app_id() -> None:
    """Set explicit Windows AppUserModelID so the taskbar displays the custom icon."""
    try:
        if sys.platform == "win32":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception as err:
        logging.getLogger("lifelane.windows").debug("Could not set AppUserModelID: %s", err)


def main() -> int:
    bundle_dir, working_dir = get_base_directories()
    args = parse_args(bundle_dir, working_dir)

    # Load environment variables
    env_path = working_dir / ".env"
    if not env_path.exists():
        env_path = bundle_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    if args.headless_smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    set_windows_app_id()
    configure_logging(working_dir)

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from raspberry_pi_app.core.config import load_config
    from raspberry_pi_app.database.connection import connect_database
    from raspberry_pi_app.database.repository import Repository
    from raspberry_pi_app.ui.main_window import MainWindow

    config = load_config(args.config)
    connection = connect_database(args.database)
    repository = Repository(connection, str(config.junction["id"]))

    app = QApplication(sys.argv[:1])
    app.setApplicationName("LifeLane")
    app.setOrganizationName("LifeLane")
    app.setApplicationDisplayName("LifeLane Traffic Signal Preemption")

    # Set Window and Application Icon
    icon_paths = [
        bundle_dir / "raspberry_pi_app" / "resources" / "icons" / "lifelane.ico",
        bundle_dir / "raspberry_pi_app" / "resources" / "icons" / "lifelane.png",
        working_dir / "raspberry_pi_app" / "resources" / "icons" / "lifelane.ico",
    ]
    for p in icon_paths:
        if p.exists():
            app_icon = QIcon(str(p))
            app.setWindowIcon(app_icon)
            break

    window = MainWindow(config, repository)

    # Ensure window icon is explicitly set on the main window instance
    for p in icon_paths:
        if p.exists():
            window.setWindowIcon(QIcon(str(p)))
            break

    window.show()

    if args.headless_smoke_test:
        from raspberry_pi_app.core.models import Approach

        window.start_simulation(Approach.NORTH)

        def finish_smoke_test() -> None:
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshot))
            window.close()
            app.quit()

        QTimer.singleShot(1800, finish_smoke_test)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
