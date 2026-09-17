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
    before_stop: bool = False
    entry_samples: int = 0
    exit_samples: int = 0


class PassageDetector:
    def __init__(self, exit_radius_metres: float, heading_tolerance_degrees: float = 60.0) -> None:
        self.exit_radius = exit_radius_metres
        self.heading_tolerance = heading_tolerance_degrees
        self._distances: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=5))
        self._states: dict[str, PassageState] = defaultdict(PassageState)

    def update(self, assessment: GPSAssessment) -> bool:
        if not assessment.valid or assessment.signed_stop_distance is None or assessment.after_exit_metres is None:
            return False
        trip = assessment.packet.trip_id
        state = self._states[trip]
        distances = self._distances[trip]
        distances.append(assessment.distance_metres)
        if assessment.signed_stop_distance > 0:
            state.before_stop = True
        inbound_heading = assessment.approach is not None and abs((assessment.packet.heading_degrees - {
            "NORTH": 180, "EAST": 270, "SOUTH": 0, "WEST": 90
        }[assessment.approach.value] + 180) % 360 - 180) <= self.heading_tolerance
        if state.before_stop and assessment.signed_stop_distance < 0 and assessment.inside_polygon and inbound_heading:
            state.entry_samples += 1
        elif not state.entered_zone:
            state.entry_samples = 0
        if state.entry_samples >= 2:
            state.entered_zone = True
        if state.crossed or not state.entered_zone or len(distances) < 3:
            return state.crossed
        recent = list(distances)[-3:]
        increasing_twice = recent[1] > recent[0] + 1.0 and recent[2] > recent[1] + 1.0
        heading_away = angular_difference(
            assessment.packet.heading_degrees, assessment.bearing_to_junction
        ) > 180.0 - self.heading_tolerance
        leaving = increasing_twice and heading_away and not assessment.inside_polygon and assessment.after_exit_metres >= self.exit_radius
        state.exit_samples = state.exit_samples + 1 if leaving else 0
        if state.exit_samples >= 3:
            state.crossed = True
        return state.crossed

    def entered_zone(self, trip_id: str) -> bool:
        return self._states[trip_id].entered_zone

    def entry_confirmations(self, trip_id: str) -> int:
        return self._states[trip_id].entry_samples

    def reset(self, trip_id: str | None = None) -> None:
        if trip_id is None:
            self._distances.clear()
            self._states.clear()
        else:
            self._distances.pop(trip_id, None)
            self._states.pop(trip_id, None)
