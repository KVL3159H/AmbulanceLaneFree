import math
from datetime import datetime, timedelta, timezone

from raspberry_pi_app.core.gps_engine import GPSEngine, angular_difference
from raspberry_pi_app.core.models import Approach


def test_north_packet_geometry(config, packet_factory):
    engine = GPSEngine(config)
    now = datetime.now(timezone.utc)
    for i, distance in enumerate([230, 220, 210, 200]):
        stamp = now + timedelta(seconds=i)
        result = engine.assess(packet_factory(Approach.NORTH, distance=distance, sequence=i+1, timestamp=stamp), stamp)
        assert result.eligible == (i == 3)
    assert result.approach is Approach.NORTH
    assert result.distance_metres == pytest.approx(200, abs=1)
    assert result.route_distance_metres == pytest.approx(180, abs=1)


def test_stale_gps_rejected(config, packet_factory):
    packet = packet_factory(timestamp=datetime.now(timezone.utc) - timedelta(seconds=10))
    result = GPSEngine(config).assess(packet)
    assert not result.valid
    assert "stale" in result.reason


def test_poor_accuracy_rejected(config, packet_factory):
    result = GPSEngine(config).assess(packet_factory(accuracy=31))
    assert not result.valid
    assert "accuracy" in result.reason


def test_duplicate_packet_rejected(config, packet_factory):
    engine = GPSEngine(config)
    packet = packet_factory(sequence=7)
    assert engine.assess(packet).valid
    duplicate = engine.assess(packet)
    assert not duplicate.valid
    assert "duplicate" in duplicate.reason


def test_moving_away_rejected(config, packet_factory):
    engine = GPSEngine(config)
    now = datetime.now(timezone.utc)
    for i, distance in enumerate([100, 110, 125]):
        stamp = now + timedelta(seconds=i)
        result = engine.assess(packet_factory(distance=distance, sequence=i+1, heading=0, timestamp=stamp), stamp)
    assert result.valid and not result.eligible
    assert "moving away" in result.reason


def test_slowly_moving_ambulance_near_junction(config, packet_factory):
    engine = GPSEngine(config)
    result = engine.assess(packet_factory(distance=80, speed=0.2, heading=90))
    assert not result.eligible
    assert not result.approaching


def test_angular_difference_wraparound():
    assert angular_difference(359, 1) == 2


def test_live_phone_real_world_gps_approach(config):
    """Verify that real-world GPS coordinates (not matching synthetic lab path) are accepted for LIVE_PHONE."""
    from raspberry_pi_app.core.models import PatientPriority, TelemetryPacket
    engine = GPSEngine(config)
    now = datetime.now(timezone.utc)
    # Moving along road towards demo junction (9.4515, 77.5535) from East at 15 m/s (1 Hz)
    # Start at distance ~220m, stepping 15m each second
    coords = []
    base_dist = 220.0
    for i in range(4):
        d = base_dist - i * 15.0
        # East approach: latitude offset by -100m (real world road offset), longitude by +d meters
        lat = 9.4515 - 100.0 / 111320
        lon = 77.5535 + d / (111320 * math.cos(math.radians(9.4515)))
        coords.append((lat, lon, 15.0))
    for i, (lat, lon, speed) in enumerate(coords):
        stamp = now + timedelta(seconds=i)
        packet = TelemetryPacket(
            schema_version=1,
            sequence_number=i + 1,
            ambulance_id="AMB-001",
            trip_id="LIVE-TRIP-1",
            latitude=lat,
            longitude=lon,
            accuracy_metres=4.0,
            speed_mps=speed,
            heading_degrees=290.0,
            patient_priority=PatientPriority.RED,
            patient_condition="TRAUMA",
            destination_hospital="Jeyaram Children's Hospital",
            emergency_active=True,
            timestamp=stamp,
            approach_side="EAST",
            source_mode="LIVE_PHONE",
        )
        result = engine.assess(packet, stamp)
        assert result.valid, f"Packet {i+1} rejected: {result.reason}"
    assert result.approach is Approach.EAST
    assert result.eligible, f"Expected eligible on final approach, got: {result.reason}"


import pytest

