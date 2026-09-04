"""Ambulance path generator which produces normal TelemetryPacket objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.config import JunctionConfig
from ..core.models import Approach, PatientPriority, TelemetryPacket
from .simulated_paths import metres_to_coordinates, offset_for_side


@dataclass
class SimulatedAmbulance:
    config: JunctionConfig
    ambulance_id: str
    trip_id: str
    starting_side: Approach
    priority: PatientPriority = PatientPriority.RED
    condition: str = "CARDIAC"
    destination: str = "Government Hospital"
    speed_mps: float = 12.0
    accuracy_metres: float = 6.0
    packet_delay_seconds: float = 1.0
    signed_distance_metres: float = 380.0
    sequence_number: int = 0
    active: bool = True
    gps_enabled: bool = True

    @property
    def finished(self) -> bool:
        return self.signed_distance_metres < -140.0

    def next_packet(self, now: datetime | None = None) -> TelemetryPacket | None:
        if not self.active or not self.gps_enabled or self.finished:
            return None
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        north, east, heading = offset_for_side(self.starting_side, self.signed_distance_metres)
        latitude, longitude = metres_to_coordinates(
            float(self.config.junction["latitude"]),
            float(self.config.junction["longitude"]),
            north,
            east,
        )
        self.sequence_number += 1
        packet = TelemetryPacket(
            schema_version=1,
            sequence_number=self.sequence_number,
            ambulance_id=self.ambulance_id,
            trip_id=self.trip_id,
            latitude=latitude,
            longitude=longitude,
            accuracy_metres=self.accuracy_metres,
            speed_mps=self.speed_mps,
            heading_degrees=heading,
            patient_priority=self.priority,
            patient_condition=self.condition,
            destination_hospital=self.destination,
            emergency_active=True,
            timestamp=now,
        )
        multiplier = float(self.config.simulation.get("speed_multiplier", 1.0))
        self.signed_distance_metres -= self.speed_mps * self.packet_delay_seconds * multiplier
        return packet
