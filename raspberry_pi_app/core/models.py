"""Domain models shared by live MQTT input and the built-in simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


from .protocol import Approach


class PatientPriority(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"

    @property
    def rank(self) -> int:
        return {self.RED: 0, self.YELLOW: 1, self.GREEN: 2}[self]


class RequestStatus(str, Enum):
    WAITING = "WAITING"
    HELD = "HELD"
    SELECTED = "SELECTED"
    ACTIVE = "ACTIVE"
    PASSED = "PASSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp must be an ISO-8601 string")
    if result.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class TelemetryPacket:
    schema_version: int
    sequence_number: int
    ambulance_id: str
    trip_id: str
    latitude: float
    longitude: float
    accuracy_metres: float
    speed_mps: float
    heading_degrees: float
    patient_priority: PatientPriority
    patient_condition: str
    destination_hospital: str
    emergency_active: bool
    timestamp: datetime
    request_id: str = ""
    destination_hospital_id: str = ""
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    route_distance_metres: float | None = None
    route_eta_seconds: float | None = None
    upcoming_junction_id: str = ""
    supported_junction_count: int = 0
    approach_side: str = ""
    direction: str = ""
    travel_heading: float | None = None
    compass_direction: str = ""
    bearing_to_junction: float | None = None
    bearing_compass: str = ""
    source_mode: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryPacket":
        return cls(
            schema_version=int(data["schemaVersion"]),
            sequence_number=int(data["sequenceNumber"]),
            ambulance_id=str(data["ambulanceId"]).strip(),
            trip_id=str(data["tripId"]).strip(),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            accuracy_metres=float(data["accuracyMetres"]),
            speed_mps=max(0.0, float(data["speedMps"])),
            heading_degrees=float(data["headingDegrees"]) % 360.0,
            patient_priority=PatientPriority(str(data["patientPriority"]).upper()),
            patient_condition=str(data["patientCondition"]).strip().upper(),
            destination_hospital=str(data["destinationHospital"]).strip(),
            emergency_active=bool(data["emergencyActive"]),
            timestamp=parse_timestamp(data["timestamp"]),
            request_id=str(data.get("requestId", "")).strip(),
            destination_hospital_id=str(data.get("destinationHospitalId", "")).strip(),
            destination_latitude=float(data["destinationLatitude"]) if data.get("destinationLatitude") is not None else None,
            destination_longitude=float(data["destinationLongitude"]) if data.get("destinationLongitude") is not None else None,
            route_distance_metres=float(data["routeDistanceMetres"]) if data.get("routeDistanceMetres") is not None else None,
            route_eta_seconds=float(data["routeEtaSeconds"]) if data.get("routeEtaSeconds") is not None else None,
            upcoming_junction_id=str(data.get("upcomingJunctionId", "")).strip(),
            supported_junction_count=max(0, int(data.get("supportedJunctionCount", 0))),
            approach_side=str(data.get("approachSide") or data.get("approach") or data.get("inboundApproach") or "").strip().upper(),
            direction=str(data.get("direction") or "").strip().upper(),
            travel_heading=float(data["travelHeading"]) if data.get("travelHeading") is not None else None,
            compass_direction=str(data.get("compassDirection") or "").strip(),
            bearing_to_junction=float(data["bearingToJunction"]) if data.get("bearingToJunction") is not None else None,
            bearing_compass=str(data.get("bearingCompass") or "").strip(),
            source_mode=str(data.get("sourceMode", "")).strip().upper(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "sequenceNumber": self.sequence_number,
            "ambulanceId": self.ambulance_id,
            "tripId": self.trip_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracyMetres": self.accuracy_metres,
            "speedMps": self.speed_mps,
            "headingDegrees": self.heading_degrees,
            "travelHeading": self.travel_heading if self.travel_heading is not None else self.heading_degrees,
            "patientPriority": self.patient_priority.value,
            "patientCondition": self.patient_condition,
            "destinationHospital": self.destination_hospital,
            "emergencyActive": self.emergency_active,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "requestId": self.request_id,
            "destinationHospitalId": self.destination_hospital_id,
            "destinationLatitude": self.destination_latitude,
            "destinationLongitude": self.destination_longitude,
            "routeDistanceMetres": self.route_distance_metres,
            "routeEtaSeconds": self.route_eta_seconds,
            "upcomingJunctionId": self.upcoming_junction_id,
            "supportedJunctionCount": self.supported_junction_count,
            "approachSide": self.approach_side,
            "direction": self.direction,
            "compassDirection": self.compass_direction,
            "bearingToJunction": self.bearing_to_junction,
            "bearingCompass": self.bearing_compass,
            "sourceMode": self.source_mode,
        }


@dataclass(frozen=True)
class GPSAssessment:
    packet: TelemetryPacket
    valid: bool
    eligible: bool
    reason: str
    distance_metres: float | None = None
    bearing_to_junction: float | None = None
    relative_bearing: float | None = None
    approach: Approach | None = None
    approaching: bool = False
    eta_seconds: float | None = None
    filtered_speed_mps: float = 0.0
    approach_confidence: float = 0.0
    signed_stop_distance: float | None = None
    after_exit_metres: float | None = None
    inside_polygon: bool = False
    route_distance_metres: float | None = None


@dataclass
class PriorityRequest:
    ambulance_id: str
    trip_id: str
    approach: Approach
    priority: PatientPriority
    condition: str
    destination: str
    distance_metres: float
    eta_seconds: float | None
    first_requested_at: datetime
    last_updated_at: datetime
    status: RequestStatus = RequestStatus.WAITING
    inside_junction: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def waiting_seconds(self) -> float:
        return max(0.0, (utc_now() - self.first_requested_at).total_seconds())
