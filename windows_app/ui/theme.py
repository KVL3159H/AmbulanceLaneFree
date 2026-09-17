"""Central visual tokens and icon helpers for the LifeLane Windows desktop UI.

Identical design language to the Raspberry Pi app — same colour palette and
spacing system — but loads Segoe UI as the preferred font family on Windows.
Icons and other shared resources are resolved from the raspberry_pi_app
resource tree so they do not need to be duplicated.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon


# ---------------------------------------------------------------------------
# Colour palette — identical tokens to raspberry_pi_app/ui/theme.py
# ---------------------------------------------------------------------------

class Color:
    BACKGROUND    = "#F8FAFC"
    NAVIGATION    = "#FFFFFF"
    SURFACE       = "#FFFFFF"
    ELEVATED      = "#F1F5F9"
    BORDER        = "#E2E8F0"
    PRIMARY       = "#1D4ED8"
    PRIMARY_HOVER = "#1E40AF"
    TEXT          = "#0F172A"
    SECONDARY     = "#475569"
    MUTED         = "#64748B"
    RED           = "#DC2626"
    AMBER         = "#D97706"
    GREEN         = "#059669"
    INFO          = "#2563EB"
    DISABLED      = "#CBD5E1"
    LAMP_OFF      = "#1E293B"
    ROAD          = "#334155"
    ROAD_EDGE     = "#64748B"
    MARKING       = "#FFFFFF"


# ---------------------------------------------------------------------------
# Spacing system — identical to raspberry_pi_app/ui/theme.py
# ---------------------------------------------------------------------------

class Space:
    XS   = 4
    SM   = 8
    MD   = 12
    LG   = 16
    XL   = 24
    XXL  = 32
    XXXL = 48


# ---------------------------------------------------------------------------
# Resource roots — delegate to the shared raspberry_pi_app assets
# ---------------------------------------------------------------------------

_WINDOWS_UI_ROOT  = Path(__file__).resolve().parent
_PROJECT_ROOT     = _WINDOWS_UI_ROOT.parents[1]
_PI_RESOURCE_ROOT = _PROJECT_ROOT / "raspberry_pi_app" / "resources"
ICON_ROOT         = _PI_RESOURCE_ROOT / "icons"
LOGO_ROOT         = _PI_RESOURCE_ROOT / "logo"


def icon(name: str) -> QIcon:
    """Return a project-owned SVG icon by name (no dependency on desktop theme)."""
    candidate = ICON_ROOT / f"{name}.svg"
    return QIcon(str(candidate)) if candidate.exists() else QIcon()


def qt_colour(value: str, alpha: int | None = None) -> QColor:
    """Create a QColor, optionally with an explicit alpha (0-255)."""
    result = QColor(value)
    if alpha is not None:
        result.setAlpha(max(0, min(255, alpha)))
    return result


# ---------------------------------------------------------------------------
# Stylesheet loader
# ---------------------------------------------------------------------------

def load_stylesheet() -> str:
    """Return the Windows QSS stylesheet as a string."""
    source = _WINDOWS_UI_ROOT / "styles.qss"
    return source.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Application font — Segoe UI on Windows, graceful fallback elsewhere
# ---------------------------------------------------------------------------

def application_font() -> QFont:
    """Register and return the best available UI font for the platform."""
    platform_fonts = (
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/seguisb.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        # Fallbacks when running on Linux (dev / CI)
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-SemiBold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    )
    for font_path in platform_fonts:
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))

    available = set(QFontDatabase.families())
    candidates = ("Segoe UI", "Noto Sans", "DejaVu Sans", "Liberation Sans", "Arial")
    family = next((name for name in candidates if name in available), "Sans Serif")
    return QFont(family, 10)


# ---------------------------------------------------------------------------
# Event classification helpers (shared with Pi app)
# ---------------------------------------------------------------------------

EVENT_CATEGORY = {
    "GPS":              "GPS",
    "APPROACH":         "GPS",
    "MQTT":             "MQTT",
    "AMBULANCE_STATUS": "MQTT",
    "NORMAL_PHASE":     "Signal",
    "STATE_TRANSITION": "Signal",
    "CYCLE":            "Signal",
    "REQUEST":          "Priority",
    "AMBULANCE_SELECTED": "Priority",
    "AMBULANCE_GREEN":  "Priority",
    "CRITICAL":         "Safety",
    "SAFE":             "Safety",
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
