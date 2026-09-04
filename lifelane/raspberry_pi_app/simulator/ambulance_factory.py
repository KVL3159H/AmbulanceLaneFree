"""Factory for unique simulated trips."""

from __future__ import annotations

from itertools import count

from ..core.config import JunctionConfig
from ..core.models import Approach, PatientPriority
from .gps_simulator import SimulatedAmbulance

_counter = count(1001)


def create_simulated_ambulance(
    config: JunctionConfig,
    side: Approach,
    *,
    ambulance_id: str | None = None,
    priority: PatientPriority = PatientPriority.RED,
    speed_mps: float | None = None,
    accuracy_metres: float | None = None,
    packet_delay_seconds: float | None = None,
) -> SimulatedAmbulance:
    number = next(_counter)
    return SimulatedAmbulance(
        config=config,
        ambulance_id=ambulance_id or f"SIM-{side.value}",
        trip_id=f"SIM-TRIP-{number}",
        starting_side=side,
        priority=priority,
        speed_mps=speed_mps or float(config.simulation["ambulance_speed_mps"]),
        accuracy_metres=accuracy_metres or float(config.simulation["gps_accuracy_metres"]),
        packet_delay_seconds=packet_delay_seconds or float(config.simulation["packet_delay_seconds"]),
    )
