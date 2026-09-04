"""Small vector ambulance icon drawn entirely with Qt."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject


class AmbulanceItem(QGraphicsObject):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label
        self.setZValue(8)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-21, -14, 42, 35)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#0f172a"), 1.5))
        painter.setBrush(QColor("#f8fafc"))
        painter.drawRoundedRect(QRectF(-20, -12, 40, 24), 5, 5)
        painter.setBrush(QColor("#38bdf8"))
        painter.drawRect(QRectF(-13, -9, 10, 7))
        painter.drawRect(QRectF(5, -9, 9, 7))
        painter.setPen(QPen(QColor("#ef4444"), 3))
        painter.drawLine(-2, -7, -2, 5)
        painter.drawLine(-8, -1, 4, -1)
        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(QRectF(-30, 14, 60, 14), 0x84, self.label)
