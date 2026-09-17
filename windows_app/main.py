"""LifeLane Windows desktop application entry point.

Forwards to the unified LifeLane desktop simulator entry point in raspberry_pi_app.main.
Preserves backward compatibility for external callers, packaging scripts, and shortcuts.
"""

from __future__ import annotations

import sys
from raspberry_pi_app.main import (
    APP_USER_MODEL_ID,
    configure_logging,
    get_base_directories,
    main,
    parse_args,
    set_windows_app_id,
)

__all__ = [
    "APP_USER_MODEL_ID",
    "configure_logging",
    "get_base_directories",
    "main",
    "parse_args",
    "set_windows_app_id",
]

if __name__ == "__main__":
    raise SystemExit(main())
