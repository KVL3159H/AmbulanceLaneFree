from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from raspberry_pi_app.core.config import load_config
from raspberry_pi_app.core.models import Approach, PatientPriority, TelemetryPacket
from raspberry_pi_app.simulator.simulated_paths import metres_to_coordinates, offset_for_side


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def packet_factory(config):
    def factory(
        side: Approach = Approach.NORTH,
        distance: float = 200.0,
        *,
        sequence: int = 1,
        ambulance_id: str = "AMB-001",
        trip_id: str = "TRIP-1",
        priority: PatientPriority = PatientPriority.RED,
        speed: float = 10.0,
        accuracy: float = 5.0,
        heading: float | None = None,
        active: bool = True,
        timestamp: datetime | None = None,
    ) -> TelemetryPacket:
        north, east, travel_heading = offset_for_side(side, distance)
        lat, lon = metres_to_coordinates(
            float(config.junction["latitude"]),
            float(config.junction["longitude"]),
            north,
            east,
        )
        return TelemetryPacket(
            schema_version=1,
            sequence_number=sequence,
            ambulance_id=ambulance_id,
            trip_id=trip_id,
            latitude=lat,
            longitude=lon,
            accuracy_metres=accuracy,
            speed_mps=speed,
            heading_degrees=travel_heading if heading is None else heading,
            patient_priority=priority,
            patient_condition="CARDIAC",
            destination_hospital="Government Hospital",
            emergency_active=active,
            timestamp=timestamp or datetime.now(timezone.utc),
        )

    return factory
