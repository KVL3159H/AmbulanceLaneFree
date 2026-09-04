"""Domain models shared by live MQTT input and the built-in simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Approach(str, Enum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"


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
            "patientPriority": self.patient_priority.value,
            "patientCondition": self.patient_condition,
            "destinationHospital": self.destination_hospital,
            "emergencyActive": self.emergency_active,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
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
