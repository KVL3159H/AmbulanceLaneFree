"""Reusable, presentation-only widgets for the LifeLane desktop interface."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import Color, Space, icon


def refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class StatusBadge(QFrame):
    def __init__(self, text: str, tone: str = "neutral", tooltip: str = "") -> None:
        super().__init__()
        self.setProperty("badge", True)
        self.setMinimumHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 9, 4)
        layout.setSpacing(6)
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(14, 14)
        self.status_icon.setScaledContents(True)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_icon)
        layout.addWidget(self.label)
        self.set_status(text, tone, tooltip)

    def set_status(self, text: str, tone: str = "neutral", tooltip: str | None = None) -> None:
        self.label.setText(text)
        self.setProperty("tone", tone)
        self.label.setProperty("tone", tone)
        icon_name = {"success": "status-success", "warning": "status-warning", "critical": "status-error", "info": "junction"}.get(tone, "status-warning")
        self.status_icon.setPixmap(icon(icon_name).pixmap(14, 14))
        if tooltip is not None:
            self.setToolTip(tooltip)
        self.setAccessibleName(text)
        refresh_style(self)
        refresh_style(self.label)

    def text(self) -> str:
        return self.label.text()


class ConnectionIndicator(StatusBadge):
    def set_connection(self, label: str, state: str) -> None:
        normalized = state.upper()
        if normalized in {"CONNECTED", "LIVE", "ONLINE", "HEALTHY"}:
            tone = "success"
        elif normalized in {"CONNECTING", "RECONNECTING", "NO DATA", "WAITING"}:
            tone = "warning"
        elif "ERROR" in normalized or "DISCONNECTED" in normalized or "LOST" in normalized:
            tone = "critical"
        else:
            tone = "neutral"
        self.set_status(f"{label}  {state.title()}", tone, f"{label} status: {state}")


class SectionCard(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectionCard")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(Space.LG, Space.LG, Space.LG, Space.LG)
        self.body.setSpacing(Space.MD)
        if title:
            title_row = QVBoxLayout()
            title_row.setSpacing(2)
            heading = QLabel(title)
            heading.setObjectName("CardTitle")
            title_row.addWidget(heading)
            if subtitle:
                supporting = QLabel(subtitle)
                supporting.setObjectName("Supporting")
                supporting.setWordWrap(True)
                title_row.addWidget(supporting)
            self.body.addLayout(title_row)


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—", unit: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
        layout.setSpacing(Space.XS)
        caption = QLabel(label)
        caption.setObjectName("MetricLabel")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("Supporting")
        layout.addWidget(caption)
        layout.addWidget(self.value_label)
        if unit:
            layout.addWidget(self.unit_label)

    def set_value(self, value: str, unit: str | None = None) -> None:
        self.value_label.setText(value)
        if unit is not None:
            self.unit_label.setText(unit)
            self.unit_label.setVisible(bool(unit))


class PrimaryButton(QPushButton):
    def __init__(self, text: str, button_icon: QIcon | None = None) -> None:
        super().__init__(text)
        self.setProperty("kind", "primary")
        if button_icon:
            self.setIcon(button_icon)


class SecondaryButton(QPushButton):
    pass


class DangerButton(QPushButton):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setProperty("kind", "danger")


class PriorityBadge(StatusBadge):
    def set_priority(self, priority: str) -> None:
        label = {"RED": "Critical", "YELLOW": "Serious", "GREEN": "Stable"}.get(priority, priority.title())
        tone = {"RED": "critical", "YELLOW": "warning", "GREEN": "success"}.get(priority, "neutral")
        self.set_status(label, tone, f"Medical priority: {label}")
        self.status_icon.setPixmap(icon("medical").pixmap(14, 14))


class EmptyState(QFrame):
    def __init__(self, title: str, detail: str) -> None:
        super().__init__()
        self.setObjectName("EmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description = QLabel(detail)
        description.setObjectName("Supporting")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(description)


class ConfirmationDialog(QDialog):
    def __init__(self, title: str, message: str, confirm_label: str, danger: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL)
        layout.setSpacing(Space.LG)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        detail = QLabel(message)
        detail.setWordWrap(True)
        detail.setObjectName("Supporting")
        layout.addWidget(heading)
        layout.addWidget(detail)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        confirm = DangerButton(confirm_label) if danger else PrimaryButton(confirm_label)
        confirm.clicked.connect(self.accept)
        buttons.addButton(confirm, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @classmethod
    def confirm(cls, parent, title: str, message: str, label: str, danger: bool = False) -> bool:
        return cls(title, message, label, danger, parent).exec() == QDialog.DialogCode.Accepted


class ToastNotification(QFrame):
    dismissed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("WarningBanner")
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.LG, Space.MD, Space.LG, Space.MD)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, message: str, duration_ms: int = 3500) -> None:
        self.message.setText(message)
        self.adjustSize()
        self.move(max(16, self.parentWidget().width() - self.width() - 24), 76)
        self.show()
        self.raise_()
        self._timer.start(duration_ms)
