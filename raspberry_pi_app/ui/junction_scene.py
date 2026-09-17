"""Efficient vector four-way junction scene for live operational telemetry."""

from __future__ import annotations

import math
import random
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from ..core.models import Approach, GPSAssessment
from ..core.signal_states import PreemptionState, SignalColour
from .ambulance_item import AmbulanceItem
from .civilian_car_item import CAR_PALETTE, CivilianCarItem
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
        self.civilian_cars: list[CivilianCarItem] = []
        self.priority_corridor: QGraphicsPathItem | None = None
        self.setBackgroundBrush(QColor(Color.ELEVATED))
        self._draw_junction()
        self._init_civilian_traffic()

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

    def _init_civilian_traffic(self) -> None:
        for car in self.civilian_cars:
            self.removeItem(car)
        self.civilian_cars.clear()
        car_idx = 1
        # Stagger 2-3 cars per approach
        for approach in Approach:
            for start_d in (40.0, 160.0):
                car = CivilianCarItem(
                    f"CIV-{car_idx}",
                    approach,
                    start_d,
                    speed_pps=75.0 + random.uniform(-10.0, 15.0),
                )
                self.addItem(car)
                self.civilian_cars.append(car)
                car_idx += 1

    def update_traffic(
        self,
        dt: float,
        signals: dict[Approach, SignalColour],
        preemption_state: PreemptionState,
        target_approach: Approach | None,
    ) -> None:
        preemption_active = preemption_state not in (PreemptionState.NORMAL, PreemptionState.FAIL_SAFE)

        # Group cars by approach
        by_side: dict[Approach, list[CivilianCarItem]] = {app: [] for app in Approach}
        for car in self.civilian_cars:
            by_side[car.side].append(car)

        lane_offset = 56.0

        for approach, cars in by_side.items():
            cars.sort(key=lambda c: c.pos_along_road, reverse=True)
            is_ns = approach in (Approach.NORTH, Approach.SOUTH)
            stop_dist = 241.0 if is_ns else 566.0
            exit_dist = 489.0 if is_ns else 814.0
            total_dist = 750.0 if is_ns else 1400.0

            for i, car in enumerate(cars):
                car_ahead_dist = (cars[i - 1].pos_along_road - car.pos_along_road) if i > 0 else None
                sig = signals.get(approach, SignalColour.RED)
                car.update_behavior(
                    dt,
                    sig,
                    preemption_active,
                    target_approach,
                    car_ahead_dist,
                    stop_dist,
                    exit_dist,
                )

                # Wrap around when leaving screen
                if car.pos_along_road > total_dist:
                    min_pos = min((c.pos_along_road for c in cars if c != car), default=120.0)
                    car.pos_along_road = min(-40.0, min_pos - 130.0)
                    car.paint_color = random.choice(CAR_PALETTE)
                    car.curr_speed = car.speed_pps

                # Map path coordinate to 2D scene space
                if approach == Approach.NORTH:
                    px = (self.CX - lane_offset) - car.yield_offset
                    py = -40.0 + car.pos_along_road
                    rot = 90.0
                elif approach == Approach.SOUTH:
                    px = (self.CX + lane_offset) + car.yield_offset
                    py = 690.0 - car.pos_along_road
                    rot = -90.0
                elif approach == Approach.EAST:
                    px = 1340.0 - car.pos_along_road
                    py = (self.CY - lane_offset) - car.yield_offset
                    rot = 180.0
                else:  # WEST
                    px = -40.0 + car.pos_along_road
                    py = (self.CY + lane_offset) + car.yield_offset
                    rot = 0.0

                car.setPos(px, py)
                car.setRotation(rot)

        # Emergency ambulance priority corridor ("Ambulance Lane Free")
        if preemption_active and target_approach:
            if self.priority_corridor is None:
                self.priority_corridor = QGraphicsPathItem()
                pen = QPen(QColor(Color.PRIMARY), 3, Qt.PenStyle.DashLine)
                pen.setDashPattern([14, 8])
                self.priority_corridor.setPen(pen)
                self.priority_corridor.setBrush(QBrush(qt_colour(Color.PRIMARY, 28)))
                self.priority_corridor.setZValue(4)
                self.addItem(self.priority_corridor)

            path = QPainterPath()
            if target_approach == Approach.NORTH:
                path.addRect(self.CX - 38, 0, 76, self.CY + self.ROAD_HALF)
            elif target_approach == Approach.SOUTH:
                path.addRect(self.CX - 38, self.CY - self.ROAD_HALF, 76, self.HEIGHT - (self.CY - self.ROAD_HALF))
            elif target_approach == Approach.EAST:
                path.addRect(self.CX - self.ROAD_HALF, self.CY - 38, self.WIDTH - (self.CX - self.ROAD_HALF), 76)
            elif target_approach == Approach.WEST:
                path.addRect(0, self.CY - 38, self.CX + self.ROAD_HALF, 76)
            self.priority_corridor.setPath(path)
            self.priority_corridor.setVisible(True)
        else:
            if self.priority_corridor:
                self.priority_corridor.setVisible(False)

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
