"""Ambulance path generator which produces normal TelemetryPacket objects."""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from datetime import datetime, timezone

from ..core.config import JunctionConfig
from ..core.models import Approach, PatientPriority, TelemetryPacket
from .simulated_paths import metres_to_coordinates, offset_for_side
from ..core.route_geometry import point_along_path, lab_path


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
    advance_after_packet: bool = True
    velocity_mps: float = 0.0
    stopped: bool = False
    reversing: bool = False
    noise_metres: float = 0.0
    network_delay_seconds: float = 0.0
    random_source: random.Random = field(default_factory=lambda: random.Random(42),repr=False)

    @property
    def extent(self): return float(self.config.raw['geometry']['route_extent_metres'])

    @property
    def path(self): return self.config.raw['geometry']['paths'].get(self.starting_side.value,lab_path(self.starting_side,self.extent))

    @property
    def exit_side(self):
        east,north=self.path[-1]
        return (Approach.EAST if east>0 else Approach.WEST) if abs(east)>abs(north) else (Approach.NORTH if north>0 else Approach.SOUTH)

    @property
    def exit_progress(self): return 200-self.extent+float(self.config.raw['geometry']['exit_progress'][self.starting_side.value])

    def advance(self, seconds, signal=None, lead_distance=float("inf")):
        import math
        from ..core.signal_states import SignalColour
        if self.stopped:
            self.velocity_mps = 0.0
            return
        if self.reversing:
            self.velocity_mps = min(self.speed_mps,self.velocity_mps+2*seconds)
            self.signed_distance_metres += self.velocity_mps*seconds
            return
        remaining = seconds
        while remaining > 1e-9:
            dt = min(.025, remaining)
            available = lead_distance
            before_stop = self.signed_distance_metres-(self.extent-float(self.config.raw['geometry']['stop_progress'][self.starting_side.value]))-.5
            if before_stop >= 0 and signal in {SignalColour.RED, SignalColour.YELLOW}:
                available = min(available, before_stop)
            available = max(0,available)
            self.velocity_mps = min(self.speed_mps,self.velocity_mps+2*dt,math.sqrt(8*available))
            movement = min(available,self.velocity_mps*dt)
            self.signed_distance_metres -= movement
            lead_distance -= movement
            remaining -= dt

    @property
    def finished(self) -> bool:
        return 200-self.signed_distance_metres > self.exit_progress+185 or (self.reversing and self.signed_distance_metres > self.extent)

    def next_packet(self, now: datetime | None = None) -> TelemetryPacket | None:
        if not self.active or not self.gps_enabled or self.finished:
            return None
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        east, north, heading = point_along_path(self.path,self.extent-self.signed_distance_metres)
        if self.reversing: heading=(heading+180)%360
        if self.noise_metres:
            north += self.random_source.gauss(0,self.noise_metres)
            east += self.random_source.gauss(0,self.noise_metres)
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
            speed_mps=self.speed_mps if self.advance_after_packet else self.velocity_mps,
            heading_degrees=heading,
            patient_priority=self.priority,
            patient_condition=self.condition,
            destination_hospital=self.destination,
            emergency_active=True,
            timestamp=now,
        )
        multiplier = float(self.config.simulation.get("speed_multiplier", 1.0))
        if self.advance_after_packet:
            self.signed_distance_metres -= self.speed_mps * self.packet_delay_seconds * multiplier
        return packet
