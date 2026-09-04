"""Multi-sample junction passage detection."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .gps_engine import angular_difference
from .models import GPSAssessment


@dataclass
class PassageState:
    entered_zone: bool = False
    crossed: bool = False


class PassageDetector:
    def __init__(self, exit_radius_metres: float, heading_tolerance_degrees: float = 60.0) -> None:
        self.exit_radius = exit_radius_metres
        self.heading_tolerance = heading_tolerance_degrees
        self._distances: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=5))
        self._states: dict[str, PassageState] = defaultdict(PassageState)

    def update(self, assessment: GPSAssessment) -> bool:
        if assessment.distance_metres is None or assessment.bearing_to_junction is None:
            return False
        trip = assessment.packet.trip_id
        state = self._states[trip]
        distances = self._distances[trip]
        distances.append(assessment.distance_metres)
        if assessment.distance_metres <= self.exit_radius:
            state.entered_zone = True
        if state.crossed or not state.entered_zone or len(distances) < 3:
            return state.crossed
        recent = list(distances)[-3:]
        increasing_twice = recent[1] > recent[0] + 1.0 and recent[2] > recent[1] + 1.0
        heading_away = angular_difference(
            assessment.packet.heading_degrees, assessment.bearing_to_junction
        ) > 180.0 - self.heading_tolerance
        if increasing_twice and heading_away:
            state.crossed = True
        return state.crossed

    def entered_zone(self, trip_id: str) -> bool:
        return self._states[trip_id].entered_zone

    def reset(self, trip_id: str | None = None) -> None:
        if trip_id is None:
            self._distances.clear()
            self._states.clear()
        else:
            self._distances.pop(trip_id, None)
            self._states.pop(trip_id, None)
