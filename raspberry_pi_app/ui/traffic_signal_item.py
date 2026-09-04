"""Professional three-lamp traffic signal graphics item."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QGraphicsObject

from ..core.signal_states import SignalColour
from .theme import Color, qt_colour


class TrafficSignalItem(QGraphicsObject):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label
        self.colour = SignalColour.RED
        self.setZValue(20)
        self.setToolTip(f"{label.title()} approach signal: red")

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-38, -58, 76, 116)

    def set_colour(self, colour: SignalColour) -> None:
        if self.colour is not colour:
            self.colour = colour
            self.setToolTip(f"{self.label.title()} approach signal: {colour.value.lower()}")
            self.update()

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = {
            SignalColour.RED: Color.RED,
            SignalColour.YELLOW: Color.AMBER,
            SignalColour.GREEN: Color.GREEN,
        }
        positions = [(-30, SignalColour.RED), (-4, SignalColour.YELLOW), (22, SignalColour.GREEN)]
        for y, state in positions:
            if self.colour is state:
                halo = QRadialGradient(0, y, 20)
                halo.setColorAt(0, qt_colour(active[state], 112))
                halo.setColorAt(1, qt_colour(active[state], 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(halo)
                painter.drawEllipse(QRectF(-20, y - 20, 40, 40))
        painter.setPen(QPen(QColor(Color.BORDER), 2))
        painter.setBrush(QColor("#111820"))
        painter.drawRoundedRect(QRectF(-16, -44, 32, 80), 8, 8)
        for y, state in positions:
            painter.setPen(QPen(QColor("#090D11"), 1.5))
            painter.setBrush(QColor(active[state] if self.colour is state else Color.LAMP_OFF))
            painter.drawEllipse(QRectF(-10, y - 10, 20, 20))
        painter.setPen(QColor(Color.TEXT))
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(-38, 42, 76, 14), Qt.AlignmentFlag.AlignCenter, f"{self.label} · {self.colour.value}")
