"""Efficient vector four-way junction scene for live operational telemetry."""

from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from ..core.models import Approach, GPSAssessment
from ..core.signal_states import SignalColour
from .ambulance_item import AmbulanceItem
from .theme import Color, qt_colour
from .traffic_signal_item import TrafficSignalItem


class JunctionScene(QGraphicsScene):
    # A wide scene matches the 65/35 control-room layout while retaining the
    # square conflict zone and all four complete approaches.
    WIDTH = 1300
    HEIGHT = 650
    CX = WIDTH / 2
    CY = HEIGHT / 2
    ROAD_HALF = 112
    GEOFENCE_PIXELS = 270

    def __init__(self, activation_radius: float, exit_radius: float) -> None:
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.activation_radius = activation_radius
        self.exit_radius = exit_radius
        self.signals: dict[Approach, TrafficSignalItem] = {}
        self.ambulances: dict[str, AmbulanceItem] = {}
        self.trails: dict[str, tuple[QGraphicsPathItem, deque[QPointF]]] = {}
        self.setBackgroundBrush(QColor(Color.ELEVATED))
        self._draw_junction()

    def _draw_junction(self) -> None:
        self.addRect(self.sceneRect(), QPen(Qt.PenStyle.NoPen), QBrush(QColor(Color.ELEVATED)))
        road = QBrush(QColor(Color.ROAD))
        no_pen = QPen(Qt.PenStyle.NoPen)
        self.addRect(QRectF(self.CX - self.ROAD_HALF, 0, self.ROAD_HALF * 2, self.HEIGHT), no_pen, road)
        self.addRect(QRectF(0, self.CY - self.ROAD_HALF, self.WIDTH, self.ROAD_HALF * 2), no_pen, road)
        edge_pen = QPen(QColor(Color.ROAD_EDGE), 2)
        for offset in (-self.ROAD_HALF, self.ROAD_HALF):
            self.addLine(self.CX + offset, 0, self.CX + offset, self.CY - self.ROAD_HALF, edge_pen)
            self.addLine(self.CX + offset, self.CY + self.ROAD_HALF, self.CX + offset, self.HEIGHT, edge_pen)
            self.addLine(0, self.CY + offset, self.CX - self.ROAD_HALF, self.CY + offset, edge_pen)
            self.addLine(self.CX + self.ROAD_HALF, self.CY + offset, self.WIDTH, self.CY + offset, edge_pen)
        lane_pen = QPen(QColor(Color.MARKING), 2, Qt.PenStyle.DashLine)
        lane_pen.setDashPattern([10, 9])
        self.addLine(self.CX, 0, self.CX, self.CY - self.ROAD_HALF - 8, lane_pen)
        self.addLine(self.CX, self.CY + self.ROAD_HALF + 8, self.CX, self.HEIGHT, lane_pen)
        self.addLine(0, self.CY, self.CX - self.ROAD_HALF - 8, self.CY, lane_pen)
        self.addLine(self.CX + self.ROAD_HALF + 8, self.CY, self.WIDTH, self.CY, lane_pen)
        stop_pen = QPen(QColor(Color.MARKING), 5)
        self.addLine(self.CX - self.ROAD_HALF + 8, self.CY - self.ROAD_HALF - 12, self.CX - 8, self.CY - self.ROAD_HALF - 12, stop_pen)
        self.addLine(self.CX + 8, self.CY + self.ROAD_HALF + 12, self.CX + self.ROAD_HALF - 8, self.CY + self.ROAD_HALF + 12, stop_pen)
        self.addLine(self.CX + self.ROAD_HALF + 12, self.CY - self.ROAD_HALF + 8, self.CX + self.ROAD_HALF + 12, self.CY - 8, stop_pen)
        self.addLine(self.CX - self.ROAD_HALF - 12, self.CY + 8, self.CX - self.ROAD_HALF - 12, self.CY + self.ROAD_HALF - 8, stop_pen)
        self._draw_crosswalks()
        self._draw_direction_arrows()
        activation_pen = QPen(qt_colour(Color.PRIMARY, 104), 2, Qt.PenStyle.DashLine)
        self.addEllipse(QRectF(self.CX - self.GEOFENCE_PIXELS, self.CY - self.GEOFENCE_PIXELS,
                               self.GEOFENCE_PIXELS * 2, self.GEOFENCE_PIXELS * 2), activation_pen)
        exit_pixels = self.GEOFENCE_PIXELS * self.exit_radius / self.activation_radius
        exit_pen = QPen(qt_colour(Color.AMBER, 120), 2, Qt.PenStyle.DotLine)
        self.addEllipse(QRectF(self.CX - exit_pixels, self.CY - exit_pixels, exit_pixels * 2, exit_pixels * 2), exit_pen)
        labels = {
            Approach.NORTH: (self.CX - 34, 12), Approach.SOUTH: (self.CX - 34, self.HEIGHT - 34),
            Approach.EAST: (self.WIDTH - 62, self.CY - 16), Approach.WEST: (12, self.CY - 16),
        }
        for side, (x, y) in labels.items():
            text = self.addText(side.value)
            text.setDefaultTextColor(QColor(Color.SECONDARY))
            font = text.font(); font.setPixelSize(11); font.setBold(True); text.setFont(font)
            text.setPos(x, y)
        north_marker = self.addText("N")
        north_marker.setDefaultTextColor(QColor(Color.PRIMARY))
        north_marker.setPos(self.WIDTH - 34, 18)
        positions = {
            Approach.NORTH: (self.CX - 148, self.CY - 156), Approach.SOUTH: (self.CX + 148, self.CY + 156),
            Approach.EAST: (self.CX + 148, self.CY - 156), Approach.WEST: (self.CX - 148, self.CY + 156),
        }
        for side, position in positions.items():
            item = TrafficSignalItem(side.value.title())
            item.setPos(*position)
            self.addItem(item)
            self.signals[side] = item
        legend = self.addText("Activation geofence  ·  Exit geofence")
        legend.setDefaultTextColor(QColor(Color.MUTED)); legend.setPos(16, self.HEIGHT - 30)

    def _draw_crosswalks(self) -> None:
        brush = QBrush(qt_colour(Color.MARKING, 170)); no_pen = QPen(Qt.PenStyle.NoPen)
        for x in range(int(self.CX - self.ROAD_HALF + 10), int(self.CX + self.ROAD_HALF - 10), 13):
            self.addRect(QRectF(x, self.CY - self.ROAD_HALF - 34, 8, 5), no_pen, brush)
            self.addRect(QRectF(x, self.CY + self.ROAD_HALF + 29, 8, 5), no_pen, brush)
        for y in range(int(self.CY - self.ROAD_HALF + 10), int(self.CY + self.ROAD_HALF - 10), 13):
            self.addRect(QRectF(self.CX - self.ROAD_HALF - 34, y, 5, 8), no_pen, brush)
            self.addRect(QRectF(self.CX + self.ROAD_HALF + 29, y, 5, 8), no_pen, brush)

    def _draw_direction_arrows(self) -> None:
        brush = QBrush(qt_colour(Color.MARKING, 187)); no_pen = QPen(Qt.PenStyle.NoPen)
        arrows = [
            QPolygonF([QPointF(self.CX - 55, 112), QPointF(self.CX - 68, 130), QPointF(self.CX - 60, 130), QPointF(self.CX - 60, 158), QPointF(self.CX - 50, 158), QPointF(self.CX - 50, 130), QPointF(self.CX - 42, 130)]),
            QPolygonF([QPointF(self.CX + 55, self.HEIGHT - 112), QPointF(self.CX + 42, self.HEIGHT - 130), QPointF(self.CX + 50, self.HEIGHT - 130), QPointF(self.CX + 50, self.HEIGHT - 158), QPointF(self.CX + 60, self.HEIGHT - 158), QPointF(self.CX + 60, self.HEIGHT - 130), QPointF(self.CX + 68, self.HEIGHT - 130)]),
            QPolygonF([QPointF(112, self.CY + 55), QPointF(130, self.CY + 42), QPointF(130, self.CY + 50), QPointF(158, self.CY + 50), QPointF(158, self.CY + 60), QPointF(130, self.CY + 60), QPointF(130, self.CY + 68)]),
            QPolygonF([QPointF(self.WIDTH - 112, self.CY - 55), QPointF(self.WIDTH - 130, self.CY - 68), QPointF(self.WIDTH - 130, self.CY - 60), QPointF(self.WIDTH - 158, self.CY - 60), QPointF(self.WIDTH - 158, self.CY - 50), QPointF(self.WIDTH - 130, self.CY - 50), QPointF(self.WIDTH - 130, self.CY - 42)]),
        ]
        for polygon in arrows:
            self.addPolygon(polygon, no_pen, brush)

    def update_signals(self, signals: dict[Approach, SignalColour]) -> None:
        for side, colour in signals.items():
            self.signals[side].set_colour(colour)

    def update_ambulance(self, assessment: GPSAssessment) -> None:
        if assessment.distance_metres is None or assessment.relative_bearing is None:
            return
        trip_id = assessment.packet.trip_id
        item = self.ambulances.get(trip_id)
        if item is None:
            simulated = assessment.packet.ambulance_id.startswith("SIM-")
            item = AmbulanceItem(assessment.packet.ambulance_id, assessment.packet.patient_priority, simulated)
            self.addItem(item); self.ambulances[trip_id] = item
            trail = QGraphicsPathItem(); trail.setPen(QPen(qt_colour(Color.PRIMARY, 153), 2, Qt.PenStyle.DashLine)); trail.setZValue(5)
            self.addItem(trail); self.trails[trip_id] = (trail, deque(maxlen=36))
        radius = min(330.0, assessment.distance_metres / self.activation_radius * self.GEOFENCE_PIXELS)
        angle = math.radians(assessment.relative_bearing)
        target = QPointF(self.CX + math.sin(angle) * radius, self.CY - math.cos(angle) * radius)
        item.set_priority(assessment.packet.patient_priority); item.set_distance(assessment.distance_metres)
        item.setRotation(assessment.packet.heading_degrees); item.setVisible(assessment.packet.emergency_active); item.animate_to(target)
        trail, points = self.trails[trip_id]; points.append(target)
        path = QPainterPath()
        if points:
            path.moveTo(points[0])
            for point in list(points)[1:]: path.lineTo(point)
        trail.setPath(path); trail.setVisible(assessment.packet.emergency_active)

    def set_selected_trip(self, trip_id: str | None) -> None:
        for key, item in self.ambulances.items(): item.set_selected(key == trip_id)

    def hide_ambulance(self, trip_id: str) -> None:
        if trip_id in self.ambulances: self.ambulances[trip_id].setVisible(False)
        if trip_id in self.trails: self.trails[trip_id][0].setVisible(False)

    def clear_ambulances(self) -> None:
        for item in self.ambulances.values(): self.removeItem(item)
        for trail, _points in self.trails.values(): self.removeItem(trail)
        self.ambulances.clear(); self.trails.clear()


class ResponsiveGraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setToolTip("Software-simulated four-way junction. No physical signal hardware is controlled.")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
