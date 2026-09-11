"""GPS validation, geometry, movement trend, and ETA processing."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque

from .config import JunctionConfig
from .eta_calculator import calculate_eta
from .models import GPSAssessment, TelemetryPacket
from .side_detector import detect_approach

EARTH_RADIUS_METRES = 6_371_000.0


def haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return EARTH_RADIUS_METRES * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.degrees(math.atan2(x, y)) % 360.0


def angular_difference(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


class GPSEngine:
    """Stateful processor; duplicate and trend state is per ambulance/trip."""

    def __init__(self, config: JunctionConfig) -> None:
        self.config = config
        self._history: dict[str, Deque[tuple[datetime, float, float]]] = defaultdict(
            lambda: deque(maxlen=8)
        )
        self._last_sequences: dict[tuple[str, str], int] = {}

    def reset(self) -> None:
        self._history.clear()
        self._last_sequences.clear()

    def history_distances(self, ambulance_id: str) -> list[float]:
        return [entry[1] for entry in self._history.get(ambulance_id, ())]

    def assess(self, packet: TelemetryPacket, now: datetime | None = None) -> GPSAssessment:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        invalid = self._basic_validation(packet, now)
        if invalid:
            return GPSAssessment(packet, False, False, invalid)

        key = (packet.ambulance_id, packet.trip_id)
        previous_sequence = self._last_sequences.get(key)
        if previous_sequence is not None and packet.sequence_number <= previous_sequence:
            return GPSAssessment(packet, False, False, "duplicate or out-of-order sequence number")
        self._last_sequences[key] = packet.sequence_number

        junction = self.config.junction
        junc_lat = getattr(self, "active_junction_lat", None) or float(junction["latitude"])
        junc_lon = getattr(self, "active_junction_lon", None) or float(junction["longitude"])

        distance = haversine_metres(
            packet.latitude,
            packet.longitude,
            junc_lat,
            junc_lon,
        )
        to_junction = initial_bearing(
            packet.latitude,
            packet.longitude,
            junc_lat,
            junc_lon,
        )
        relative = initial_bearing(
            junc_lat,
            junc_lon,
            packet.latitude,
            packet.longitude,
        )
        approach = detect_approach(relative)
        history = self._history[packet.ambulance_id]
        history.append((packet.timestamp, distance, packet.speed_mps))

        detection = self.config.detection
        activation = float(detection["activation_radius_metres"])
        immediate_radius = float(detection["immediate_activation_radius_metres"])
        immediate = distance <= immediate_radius
        heading_toward = angular_difference(packet.heading_degrees, to_junction) <= float(
            detection["heading_tolerance_degrees"]
        )
        distances = [value[1] for value in history]
        trend = self._trend(distances)
        clearly_away = trend == "away" and not heading_toward
        approaching = (
            (heading_toward and trend in ("toward", "unknown"))
            or (immediate and trend != "away")
            or (immediate and packet.speed_mps < 2.0 and trend != "away")
            or (len(distances) <= 2 and heading_toward)
        )

        eta, speed = calculate_eta(
            distance,
            [value[2] for value in history][-5:],
            immediate=immediate,
            minimum_assumed_speed_mps=float(detection.get("minimum_assumed_speed_mps", 2.0)),
        )
        common = dict(
            distance_metres=distance,
            bearing_to_junction=to_junction,
            relative_bearing=relative,
            approach=approach,
            approaching=approaching,
            eta_seconds=eta,
            filtered_speed_mps=speed,
        )
        if distance > activation:
            return GPSAssessment(packet, True, False, "outside activation radius", **common)
        if clearly_away or not approaching:
            reason = "ambulance is moving away" if clearly_away else "insufficient approaching movement"
            return GPSAssessment(packet, True, False, reason, **common)
        return GPSAssessment(packet, True, True, "eligible", **common)

    def _basic_validation(self, packet: TelemetryPacket, now: datetime) -> str | None:
        detection = self.config.detection
        if packet.schema_version != 1:
            return "unsupported schema version"
        if not packet.ambulance_id:
            return "unauthorized ambulance ID"
        is_known = packet.ambulance_id in self.config.authorized_ids
        is_standard = packet.ambulance_id.startswith(("AMB-", "SIM-", "DRV-", "EMG-"))
        if not (is_known or is_standard):
            return "unauthorized ambulance ID"
        if not packet.trip_id:
            return "trip ID is required"
        if not (-90.0 <= packet.latitude <= 90.0 and -180.0 <= packet.longitude <= 180.0):
            return "impossible coordinates"
        if not math.isfinite(packet.latitude) or not math.isfinite(packet.longitude):
            return "impossible coordinates"
        if not all(math.isfinite(value) for value in (
            packet.accuracy_metres, packet.speed_mps, packet.heading_degrees
        )):
            return "non-finite GPS measurement"
        if packet.accuracy_metres < 0 or packet.accuracy_metres > float(
            detection["maximum_accuracy_metres"]
        ):
            return "GPS accuracy is too poor"
        age = (now - packet.timestamp).total_seconds()
        # Allow up to 60 seconds age to accommodate clock skew on mobile devices, and 10s future drift
        max_age = max(60.0, float(detection.get("maximum_packet_age_seconds", 5.0)))
        if age > max_age or age < -10.0:
            return "GPS packet is stale or has an invalid future timestamp"
        if not packet.emergency_active:
            return "emergency trip is inactive"
        return None

    @staticmethod
    def _trend(distances: list[float]) -> str:
        if len(distances) < 2:
            return "unknown"
        recent = distances[-5:]
        delta = recent[-1] - recent[0]
        steps = [b - a for a, b in zip(recent, recent[1:])]
        increasing = sum(step > 1.0 for step in steps)
        decreasing = sum(step < -1.0 for step in steps)
        if delta > 3.0 and increasing >= max(1, len(steps) // 2):
            return "away"
        if delta < -2.0 and decreasing >= max(1, len(steps) // 2):
            return "toward"
        return "steady"
