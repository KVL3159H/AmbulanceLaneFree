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
from .route_geometry import passage_geometry

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
        self._last_packets = {}
        self._confirmed_sides = {}
        self._confirmations = defaultdict(int)
        self._candidate_sides = {}
        self._headings = defaultdict(lambda: deque(maxlen=3))

    def reset(self) -> None:
        self._history.clear()
        self._last_sequences.clear()
        self._last_packets.clear()
        self._confirmed_sides.clear()
        self._confirmations.clear()
        self._candidate_sides.clear()
        self._headings.clear()

    def history_distances(self, ambulance_id: str) -> list[float]:
        entries = [entry for key,history in self._history.items() if key[0]==ambulance_id for entry in history]
        return [entry[1] for entry in sorted(entries,key=lambda entry:entry[0])[-8:]]

    def reset_trip(self, ambulance_id, trip_id):
        key=(ambulance_id,trip_id)
        for mapping in (self._history,self._last_sequences,self._last_packets,self._confirmed_sides,self._confirmations,self._candidate_sides,self._headings):
            mapping.pop(key,None)

    def assess(self, packet: TelemetryPacket, now: datetime | None = None) -> GPSAssessment:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        invalid = self._basic_validation(packet, now)
        if invalid:
            return GPSAssessment(packet, False, False, invalid)

        key = (packet.ambulance_id, packet.trip_id)
        previous_sequence = self._last_sequences.get(key)
        if previous_sequence is not None and packet.sequence_number <= previous_sequence:
            return GPSAssessment(packet, False, False, "duplicate or out-of-order sequence number")
        previous = self._last_packets.get(key)
        if previous:
            delta = (packet.timestamp - previous.timestamp).total_seconds()
            if delta <= 0:
                return GPSAssessment(packet, False, False, "out-of-order GPS timestamp")
            if delta > float(self.config.detection["maximum_packet_age_seconds"]):
                self._history[key].clear()
                self._confirmations[key] = 0
                self._headings[key].clear()
            displacement = haversine_metres(previous.latitude, previous.longitude, packet.latitude, packet.longitude)
            if displacement > 70 * delta + previous.accuracy_metres + packet.accuracy_metres:
                return GPSAssessment(packet, False, False, "impossible GPS jump")
        self._last_sequences[key] = packet.sequence_number
        self._last_packets[key] = packet

        junction = self.config.junction
        junc_lat = float(junction["latitude"])
        junc_lon = float(junction["longitude"])

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
        approach = self._confirmed_sides.get(key, detect_approach(relative))
        if self._candidate_sides.get(key) != approach:
            self._confirmations[key] = 0
        self._candidate_sides[key] = approach
        projection, signed_stop, after_exit, inside = passage_geometry(self.config, packet, approach)
        history = self._history[key]
        history.append((packet.timestamp, signed_stop, packet.speed_mps))

        detection = self.config.detection
        activation = float(detection["activation_radius_metres"])
        if packet.speed_mps >= float(detection.get("minimum_heading_speed_mps", 2)):
            self._headings[key].append(packet.heading_degrees)
        headings = self._headings[key]
        smoothed_heading = math.degrees(math.atan2(sum(math.sin(math.radians(h)) for h in headings),
                                                  sum(math.cos(math.radians(h)) for h in headings))) % 360 if headings else packet.heading_degrees
        heading_toward = angular_difference(smoothed_heading, projection.heading) <= float(
            detection["heading_tolerance_degrees"])
        distances = [value[1] for value in history]
        trend = self._trend(distances)
        moving = packet.speed_mps >= float(detection.get("minimum_heading_speed_mps", 2))
        route_match = projection.lateral <= float(detection.get("route_corridor_metres", 40))
        if not route_match:
            history.pop()
            if previous is not None:
                self._last_packets[key] = previous
            else:
                self._last_packets.pop(key, None)
            self._confirmations[key] = 0
            return GPSAssessment(packet, False, False, "outside configured route corridor")
        approaching = heading_toward and moving and trend == "toward" and signed_stop > 0
        clearly_away = not heading_toward and moving
        self._confirmations[key] = self._confirmations[key] + 1 if approaching else 0
        confidence = (25 * route_match + 25 * (heading_toward and moving) +
                      20 * (trend == "toward") + 15 * (packet.accuracy_metres <= 15) +
                      15 * (len(history) >= 3 and moving))
        confirmed = self._confirmations[key] >= int(detection.get("consecutive_approach_samples", 3)) and confidence >= 80
        if confirmed:
            self._confirmed_sides[key] = approach
        immediate = False
        eta, speed = calculate_eta(
            max(0, signed_stop),
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
            approach_confidence=confidence,
            signed_stop_distance=signed_stop,
            after_exit_metres=after_exit,
            inside_polygon=inside,
            route_distance_metres=max(0, signed_stop),
        )
        if distance > float(detection.get("monitoring_distance_metres", 1000)) or (signed_stop > activation and (eta is None or eta > float(detection.get("request_eta_seconds", 45)))):
            return GPSAssessment(packet, True, False, "outside activation radius", **common)
        if clearly_away or not approaching:
            reason = "ambulance is moving away" if clearly_away else "insufficient approaching movement"
            return GPSAssessment(packet, True, False, reason, **common)
        if not confirmed:
            return GPSAssessment(packet, True, False, "Confirming ambulance approach", **common)
        return GPSAssessment(packet, True, True, "eligible", **common)

    def _basic_validation(self, packet: TelemetryPacket, now: datetime) -> str | None:
        detection = self.config.detection
        if packet.schema_version != 1:
            return "unsupported schema version"
        if not packet.ambulance_id:
            return "unauthorized ambulance ID"
        is_known = packet.ambulance_id in self.config.authorized_ids
        if not is_known:
            return "unauthorized ambulance ID"
        if not 0 <= packet.speed_mps <= float(detection.get("maximum_speed_mps", 70)):
            return "physically unrealistic speed"
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
        max_age = float(detection.get("maximum_packet_age_seconds", 5.0))
        if age > max_age or age < -2.0:
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
