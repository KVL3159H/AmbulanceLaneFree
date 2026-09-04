"""LifeLane desktop application entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="LifeLane native junction simulator")
    parser.add_argument("--config", type=Path, default=project_root / "config" / "junction.yaml")
    parser.add_argument("--database", type=Path, default=project_root / "data" / "lifelane.db")
    parser.add_argument("--headless-smoke-test", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--window-size", choices=["1440x900", "1100x700"], default="1440x900")
    parser.add_argument("--fullscreen-smoke", action="store_true")
    return parser.parse_args()


def configure_logging(project_root: Path) -> None:
    log_directory = project_root / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_directory / "lifelane.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    if args.headless_smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from raspberry_pi_app.core.config import load_config
    from raspberry_pi_app.database.connection import connect_database
    from raspberry_pi_app.database.repository import Repository
    from raspberry_pi_app.ui.main_window import MainWindow

    configure_logging(project_root)
    config = load_config(args.config)
    connection = connect_database(args.database)
    repository = Repository(connection, str(config.junction["id"]))
    app = QApplication(sys.argv[:1])
    app.setApplicationName("LifeLane")
    window = MainWindow(config, repository)
    if args.headless_smoke_test:
        width, height = (int(part) for part in args.window_size.split("x"))
        window.resize(width, height)
    window.show()
    if args.headless_smoke_test:
        from raspberry_pi_app.core.models import Approach

        window.enable_simulation_mode()
        window.start_simulation(Approach.NORTH)
        window.simulations[-1].signed_distance_metres = 145.0
        window.start_simulation(Approach.EAST, "SIM-SECOND")
        window.simulations[-1].signed_distance_metres = 210.0
        if args.fullscreen_smoke:
            window.showFullScreen()

        def finish_smoke_test() -> None:
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshot))
            window.close()
            app.quit()

        QTimer.singleShot(2400, finish_smoke_test)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
