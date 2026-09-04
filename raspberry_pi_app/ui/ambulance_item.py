"""Animated vector ambulance used by live and simulated telemetry."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject

from ..core.models import PatientPriority
from .theme import Color


class AmbulanceItem(QGraphicsObject):
    def __init__(self, label: str, priority: PatientPriority, simulated: bool = False) -> None:
        super().__init__()
        self.label = label
        self.priority = priority
        self.simulated = simulated
        self.distance_text = "—"
        self.selected = False
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(550)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._move_frame)
        self.setZValue(15)
        self.setToolTip(label)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-48, -25, 96, 60)

    def set_priority(self, priority: PatientPriority) -> None:
        if priority is not self.priority:
            self.priority = priority
            self.update()

    def set_selected(self, selected: bool) -> None:
        if selected != self.selected:
            self.selected = selected
            self.update()

    def animate_to(self, point: QPointF) -> None:
        if self.pos() == QPointF():
            self.setPos(point)
            return
        self._animation.stop()
        self._animation.setStartValue(self.pos())
        self._animation.setEndValue(point)
        self._animation.start()

    def _move_frame(self, value: QPointF) -> None:
        self.setPos(value)

    def set_distance(self, distance_metres: float) -> None:
        text = f"{distance_metres:.0f} m"
        if text != self.distance_text:
            self.distance_text = text
            self.setToolTip(f"{self.label}, {text} from junction")
            self.update()

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = {
            PatientPriority.RED: Color.RED,
            PatientPriority.YELLOW: Color.AMBER,
            PatientPriority.GREEN: Color.GREEN,
        }[self.priority]
        if self.selected:
            painter.setPen(QPen(QColor(Color.PRIMARY), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(-26, -17, 52, 34), 9, 9)
        painter.setPen(QPen(QColor(outline), 2.2))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(QRectF(-20, -11, 40, 23), 5, 5)
        painter.setBrush(QColor(Color.INFO))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(-15, -7, 10, 7))
        painter.drawRect(QRectF(7, -7, 8, 7))
        painter.setPen(QPen(QColor(Color.RED), 2.5))
        painter.drawLine(-1, -7, -1, 7)
        painter.drawLine(-7, 0, 5, 0)
        painter.setBrush(QColor("#1E293B"))
        painter.setPen(QPen(QColor(Color.SECONDARY), 1))
        painter.drawEllipse(QRectF(-15, 8, 7, 7))
        painter.drawEllipse(QRectF(9, 8, 7, 7))
        painter.setPen(QColor(Color.TEXT))
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        suffix = " · SIMULATED" if self.simulated else ""
        painter.drawText(QRectF(-48, 20, 96, 14), Qt.AlignmentFlag.AlignCenter, f"{self.label} · {self.distance_text}{suffix}")
