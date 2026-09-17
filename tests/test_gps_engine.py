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


import pytest
