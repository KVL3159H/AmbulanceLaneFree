"""Central visual tokens and icon helpers for the LifeLane desktop UI."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon


class Color:
    BACKGROUND = "#F8FAFC"
    NAVIGATION = "#FFFFFF"
    SURFACE = "#FFFFFF"
    ELEVATED = "#F1F5F9"
    BORDER = "#E2E8F0"
    PRIMARY = "#1D4ED8"
    PRIMARY_HOVER = "#1E40AF"
    TEXT = "#0F172A"
    SECONDARY = "#475569"
    MUTED = "#64748B"
    RED = "#DC2626"
    AMBER = "#D97706"
    GREEN = "#059669"
    INFO = "#2563EB"
    DISABLED = "#CBD5E1"
    LAMP_OFF = "#1E293B"
    ROAD = "#334155"
    ROAD_EDGE = "#64748B"
    MARKING = "#FFFFFF"


class Space:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    XXXL = 48


RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"
ICON_ROOT = RESOURCE_ROOT / "icons"
LOGO_ROOT = RESOURCE_ROOT / "logo"


def icon(name: str) -> QIcon:
    """Return a project-owned SVG icon without depending on a desktop icon theme."""
    candidate = ICON_ROOT / f"{name}.svg"
    return QIcon(str(candidate)) if candidate.exists() else QIcon()


def qt_colour(value: str, alpha: int | None = None) -> QColor:
    """Create a Qt colour without ambiguous #AARRGGBB string parsing."""
    result = QColor(value)
    if alpha is not None:
        result.setAlpha(max(0, min(255, alpha)))
    return result


def load_stylesheet() -> str:
    source = Path(__file__).with_name("styles.qss")
    return source.read_text(encoding="utf-8")


def application_font() -> QFont:
    # Headless Qt on Windows (used by smoke tests and CI) can start without a
    # populated system font database. Register an installed platform font
    # explicitly; on Raspberry Pi OS the normal database path remains the
    # preferred source and DejaVu Sans is the dependable fallback.
    platform_fonts = (
        (
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/seguisb.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
        )
        if sys.platform == "win32"
        else (
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-SemiBold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        )
    )
    for font_path in platform_fonts:
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
    available = set(QFontDatabase.families())
    candidates = ("Segoe UI", "Arial") if sys.platform == "win32" else ("Noto Sans", "DejaVu Sans", "Liberation Sans")
    family = next((name for name in candidates if name in available), "Sans Serif")
    return QFont(family, 10)


EVENT_CATEGORY = {
    "GPS": "GPS",
    "APPROACH": "GPS",
    "MQTT": "MQTT",
    "AMBULANCE_STATUS": "MQTT",
    "NORMAL_PHASE": "Signal",
    "STATE_TRANSITION": "Signal",
    "CYCLE": "Signal",
    "REQUEST": "Priority",
    "AMBULANCE_SELECTED": "Priority",
    "AMBULANCE_GREEN": "Priority",
    "CRITICAL": "Safety",
    "SAFE": "Safety",
}


def event_category(event_type: str) -> str:
    upper = event_type.upper()
    for prefix, category in EVENT_CATEGORY.items():
        if upper.startswith(prefix):
            return category
    return "System"


def event_severity(event_type: str) -> str:
    upper = event_type.upper()
    if "CRITICAL" in upper or "FAIL_SAFE" in upper:
        return "critical"
    if any(word in upper for word in ("LOST", "REJECTED", "ERROR", "CANCELLED", "PAUSED")):
        return "warning"
    if any(word in upper for word in ("CONNECTED", "ACCEPTED", "SELECTED", "GREEN", "RESTORED", "STARTED")):
        return "success"
    return "info"
