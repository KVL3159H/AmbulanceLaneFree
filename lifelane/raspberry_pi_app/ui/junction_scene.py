"""Native QGraphicsScene four-way junction visualisation."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsTextItem, QGraphicsView

from ..core.models import Approach, GPSAssessment
from ..core.signal_states import SignalColour
from .ambulance_item import AmbulanceItem
from .traffic_signal_item import TrafficSignalItem


class JunctionScene(QGraphicsScene):
    WIDTH = 760
    HEIGHT = 600
    CX = WIDTH / 2
    CY = HEIGHT / 2

    def __init__(self, activation_radius: float, exit_radius: float) -> None:
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.activation_radius = activation_radius
        self.exit_radius = exit_radius
        self.signals: dict[Approach, TrafficSignalItem] = {}
        self.ambulances: dict[str, AmbulanceItem] = {}
        self.setBackgroundBrush(QColor("#0b1220"))
        self._draw_junction()

    def _draw_junction(self) -> None:
        road = QColor("#334155")
        verge = QColor("#166534")
        self.addRect(QRectF(0, 0, self.WIDTH, self.HEIGHT), QPen(Qt.PenStyle.NoPen), QBrush(verge))
        self.addRect(QRectF(self.CX - 105, 0, 210, self.HEIGHT), QPen(Qt.PenStyle.NoPen), QBrush(road))
        self.addRect(QRectF(0, self.CY - 105, self.WIDTH, 210), QPen(Qt.PenStyle.NoPen), QBrush(road))
        self.addRect(QRectF(self.CX - 105, self.CY - 105, 210, 210), QPen(QColor("#94a3b8"), 2), QBrush(QColor("#475569")))
        lane_pen = QPen(QColor("#f8fafc"), 2, Qt.PenStyle.DashLine)
        self.addLine(self.CX, 0, self.CX, self.CY - 110, lane_pen)
        self.addLine(self.CX, self.CY + 110, self.CX, self.HEIGHT, lane_pen)
        self.addLine(0, self.CY, self.CX - 110, self.CY, lane_pen)
        self.addLine(self.CX + 110, self.CY, self.WIDTH, self.CY, lane_pen)
        boundary_pen = QPen(QColor("#38bdf8"), 2, Qt.PenStyle.DashLine)
        exit_pen = QPen(QColor("#f59e0b"), 2, Qt.PenStyle.DotLine)
        self.addEllipse(QRectF(self.CX - 255, self.CY - 255, 510, 510), boundary_pen)
        exit_pixels = 255 * self.exit_radius / self.activation_radius
        self.addEllipse(QRectF(self.CX - exit_pixels, self.CY - exit_pixels, exit_pixels * 2, exit_pixels * 2), exit_pen)
        labels = {
            Approach.NORTH: (self.CX - 28, 8),
            Approach.SOUTH: (self.CX - 28, self.HEIGHT - 30),
            Approach.EAST: (self.WIDTH - 55, self.CY - 15),
            Approach.WEST: (8, self.CY - 15),
        }
        for side, (x, y) in labels.items():
            text = self.addText(side.value.title())
            text.setDefaultTextColor(QColor("#e2e8f0"))
            text.setPos(x, y)
        positions = {
            Approach.NORTH: (self.CX - 135, self.CY - 135),
            Approach.SOUTH: (self.CX + 135, self.CY + 135),
            Approach.EAST: (self.CX + 135, self.CY - 135),
            Approach.WEST: (self.CX - 135, self.CY + 135),
        }
        for side, position in positions.items():
            item = TrafficSignalItem(side.value)
            item.setPos(*position)
            self.addItem(item)
            self.signals[side] = item
        legend = self.addText("Activation boundary  •  Exit boundary")
        legend.setDefaultTextColor(QColor("#cbd5e1"))
        legend.setPos(12, self.HEIGHT - 28)

    def update_signals(self, signals: dict[Approach, SignalColour]) -> None:
        for side, colour in signals.items():
            self.signals[side].set_colour(colour)

    def update_ambulance(self, assessment: GPSAssessment) -> None:
        if assessment.distance_metres is None or assessment.relative_bearing is None:
            return
        trip_id = assessment.packet.trip_id
        item = self.ambulances.get(trip_id)
        if item is None:
            item = AmbulanceItem(assessment.packet.ambulance_id)
            self.addItem(item)
            self.ambulances[trip_id] = item
        radius = min(310.0, assessment.distance_metres / self.activation_radius * 255.0)
        angle = math.radians(assessment.relative_bearing)
        item.setPos(self.CX + math.sin(angle) * radius, self.CY - math.cos(angle) * radius)
        item.setRotation(assessment.packet.heading_degrees)
        item.setVisible(assessment.packet.emergency_active)

    def clear_ambulances(self) -> None:
        for item in self.ambulances.values():
            self.removeItem(item)
        self.ambulances.clear()


class ResponsiveGraphicsView(QGraphicsView):
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
