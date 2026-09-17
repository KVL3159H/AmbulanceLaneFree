"""Civilian traffic vehicles for junction simulation.

Simulates normal city vehicles (sedans, SUVs, hatchbacks, vans) that:
1. Obey alternating traffic signals (stop at red/amber, proceed on green).
2. Queue safely behind preceding vehicles.
3. Dynamically yield and pull over to the road shoulder when an emergency
   ambulance approaches ("Ambulance Lane Free"), clearing the central lane.
4. Smoothly resume normal travel once the ambulance passes and signals recover.
"""

from __future__ import annotations

import random
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject

from ..core.models import Approach
from ..core.signal_states import SignalColour
from .theme import Color


CAR_PALETTE = [
    "#3B82F6",  # Sapphire Blue
    "#10B981",  # Emerald
    "#F59E0B",  # Amber Gold
    "#8B5CF6",  # Purple
    "#EF4444",  # Crimson
    "#64748B",  # Slate
    "#E2E8F0",  # Pearl White
    "#F97316",  # Coral
    "#06B6D4",  # Cyan
    "#84CC16",  # Lime
]

CAR_MODELS = [
    ("sedan", 38, 19),
    ("suv", 42, 22),
    ("compact", 32, 17),
    ("van", 46, 22),
]


class CivilianCarItem(QGraphicsObject):
    """Vector graphic civilian vehicle that obeys traffic signals and yields to ambulances."""

    def __init__(
        self,
        car_id: str,
        side: Approach,
        start_distance: float,
        speed_pps: float = 85.0,
        model: str | None = None,
        color: str | None = None,
    ) -> None:
        super().__init__()
        self.car_id = car_id
        self.side = side
        self.pos_along_road = start_distance  # distance from spawn point along travel path
        self.speed_pps = speed_pps
        self.curr_speed = speed_pps
        self.yield_offset = 0.0  # lateral offset when pulling over (pixels)
        self.target_yield_offset = 0.0
        self.is_yielding = false = False
        self.is_braking = False
        self.blink_state = False
        self._blink_counter = 0

        # Model & Appearance
        chosen_model = next((m for m in CAR_MODELS if m[0] == model), random.choice(CAR_MODELS))
        self.model_type, self.car_length, self.car_width = chosen_model
        self.paint_color = color or random.choice(CAR_PALETTE)
        self.setZValue(10)
        self.setToolTip(f"Civilian Vehicle ({self.model_type.upper()}) · {side.value}")

    def boundingRect(self) -> QRectF:  # noqa: N802
        half_l = self.car_length / 2 + 6
        half_w = self.car_width / 2 + 6
        return QRectF(-half_l, -half_w, half_l * 2, half_w * 2)

    def update_behavior(
        self,
        dt: float,
        signal: SignalColour,
        preemption_active: bool,
        preempted_side: Approach | None,
        car_ahead_dist: float | None,
        stop_line_dist: float,
        junction_exit_dist: float,
    ) -> None:
        """Update physics, signal compliance, following distance, and ambulance yielding."""
        self._blink_counter += dt
        if self._blink_counter >= 0.35:
            self._blink_counter = 0.0
            self.blink_state = not self.blink_state

        target_speed = self.speed_pps
        is_before_junction = self.pos_along_road < stop_line_dist
        is_inside_junction = stop_line_dist <= self.pos_along_road <= junction_exit_dist

        # 1. Ambulance Yielding ("Ambulance Lane Free")
        # If preemption is active for this approach, cars pull to shoulder and stop
        is_ambulance_approach = (preemption_active and preempted_side == self.side)
        if is_ambulance_approach:
            if is_before_junction:
                self.target_yield_offset = 24.0  # Steer to road shoulder
                target_speed = 0.0  # Stop to open free lane
                self.is_yielding = True
            elif is_inside_junction:
                # Quickly clear conflict zone
                target_speed = self.speed_pps * 1.3
                self.target_yield_offset = 0.0
                self.is_yielding = False
            else:
                # Past junction, continue moving
                self.target_yield_offset = 0.0
                self.is_yielding = False
        else:
            self.target_yield_offset = 0.0
            self.is_yielding = False

            # 2. Signal Compliance (Normal Alternating Traffic Cycle)
            if is_before_junction:
                dist_to_stop = stop_line_dist - self.pos_along_road
                if dist_to_stop <= 160:
                    if signal in (SignalColour.RED, SignalColour.YELLOW):
                        # Slow down and stop at stop line
                        if dist_to_stop <= 10:
                            target_speed = 0.0
                        else:
                            target_speed = min(self.speed_pps, (dist_to_stop / 160.0) * self.speed_pps)
                    elif signal == SignalColour.GREEN:
                        target_speed = self.speed_pps

        # 3. Following distance (Queue behind car ahead)
        if car_ahead_dist is not None:
            min_gap = self.car_length + 18
            if car_ahead_dist < min_gap:
                target_speed = 0.0
            elif car_ahead_dist < min_gap + 70:
                target_speed = min(target_speed, (car_ahead_dist - min_gap) / 70.0 * self.speed_pps)

        # Smooth steering transition (yield offset)
        offset_diff = self.target_yield_offset - self.yield_offset
        self.yield_offset += offset_diff * min(1.0, dt * 5.0)

        # Smooth speed transition (braking vs acceleration)
        if target_speed < self.curr_speed:
            self.curr_speed = max(target_speed, self.curr_speed - 180.0 * dt)
            self.is_braking = True
        else:
            self.curr_speed = min(target_speed, self.curr_speed + 90.0 * dt)
            self.is_braking = False

        # Move along road
        self.pos_along_road += self.curr_speed * dt
        self.update()

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        half_l = self.car_length / 2
        half_w = self.car_width / 2

        # Headlight beam glow when moving
        if self.curr_speed > 2.0:
            beam_brush = QBrush(QColor(255, 255, 200, 30))
            painter.setBrush(beam_brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(QRectF(half_l - 4, -half_w - 6, 28, half_w * 2 + 12), -30 * 16, 60 * 16)

        # Car Chassis / Body
        body_color = QColor(self.paint_color)
        painter.setBrush(QBrush(body_color))
        painter.setPen(QPen(body_color.darker(150), 1.5))
        painter.drawRoundedRect(QRectF(-half_l, -half_w, self.car_length, self.car_width), 4, 4)

        # Cabin / Roof
        roof_l = self.car_length * 0.52
        roof_w = self.car_width * 0.76
        painter.setBrush(QBrush(QColor(20, 26, 38)))
        painter.setPen(QPen(QColor(50, 60, 80), 1))
        painter.drawRoundedRect(QRectF(-roof_l / 2 - 1, -roof_w / 2, roof_l, roof_w), 3, 3)

        # Front Windshield
        painter.setBrush(QBrush(QColor(120, 180, 240, 160)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(roof_l / 2 - 4, -roof_w / 2 + 1, 4, roof_w - 2), 1, 1)

        # Rear Windshield
        painter.setBrush(QBrush(QColor(80, 120, 180, 120)))
        painter.drawRoundedRect(QRectF(-roof_l / 2, -roof_w / 2 + 1, 3, roof_w - 2), 1, 1)

        # Headlights
        painter.setBrush(QBrush(QColor(255, 255, 220)))
        painter.drawEllipse(QRectF(half_l - 2, -half_w + 1.5, 2.5, 3))
        painter.drawEllipse(QRectF(half_l - 2, half_w - 4.5, 2.5, 3))

        # Brake Lights / Tail Lights
        if self.is_braking or self.curr_speed < 2.0:
            tail_color = QColor(255, 30, 40)
            painter.setPen(QPen(QColor(255, 50, 50, 160), 2))
        else:
            tail_color = QColor(160, 20, 20)
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(tail_color))
        painter.drawRoundedRect(QRectF(-half_l, -half_w + 1.5, 2.5, 3.5), 1, 1)
        painter.drawRoundedRect(QRectF(-half_l, half_w - 5.0, 2.5, 3.5), 1, 1)

        # Hazard blinkers when yielding for ambulance
        if self.is_yielding and self.blink_state:
            amber = QColor(255, 176, 32)
            painter.setBrush(QBrush(amber))
            painter.setPen(QPen(amber, 1))
            painter.drawEllipse(QRectF(half_l - 3, -half_w - 1, 3, 3))
            painter.drawEllipse(QRectF(half_l - 3, half_w - 2, 3, 3))
            painter.drawEllipse(QRectF(-half_l, -half_w - 1, 3, 3))
            painter.drawEllipse(QRectF(-half_l, half_w - 2, 3, 3))
