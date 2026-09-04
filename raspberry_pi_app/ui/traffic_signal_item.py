"""Graphical three-lamp signal head."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject

from ..core.signal_states import SignalColour


class TrafficSignalItem(QGraphicsObject):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label
        self.colour = SignalColour.RED
        self.setZValue(10)

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        return QRectF(-18, -48, 36, 96)

    def set_colour(self, colour: SignalColour) -> None:
        if self.colour is not colour:
            self.colour = colour
            self.update()

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#111827"), 2))
        painter.setBrush(QColor("#1f2937"))
        painter.drawRoundedRect(QRectF(-16, -45, 32, 75), 7, 7)
        positions = [(-31, SignalColour.RED, "#ef4444"), (-7, SignalColour.YELLOW, "#facc15"), (17, SignalColour.GREEN, "#22c55e")]
        for y, state, active in positions:
            painter.setPen(QPen(QColor("#0b1220"), 1))
            painter.setBrush(QColor(active if self.colour is state else "#374151"))
            painter.drawEllipse(QRectF(-10, y - 8, 20, 20))
        painter.setPen(QColor("#e5e7eb"))
        painter.drawText(QRectF(-18, 32, 36, 15), 0x84, self.label[0])
