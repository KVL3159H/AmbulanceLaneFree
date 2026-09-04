"""SQLite connection factory."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schema import SCHEMA_SQL


def connect_database(path: str | Path) -> sqlite3.Connection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    connection.commit()
    return connection
