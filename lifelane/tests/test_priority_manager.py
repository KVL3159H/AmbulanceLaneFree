from dataclasses import replace
from datetime import datetime, timedelta, timezone

from raspberry_pi_app.core.gps_engine import GPSEngine
from raspberry_pi_app.core.models import PatientPriority
from raspberry_pi_app.core.priority_manager import PriorityManager


def add(manager, engine, packet, now):
    assessment = engine.assess(packet, now=now)
    if not assessment.eligible and "insufficient approaching" in assessment.reason:
        centre_lat = float(engine.config.junction["latitude"])
        centre_lon = float(engine.config.junction["longitude"])
        packet = replace(
            packet,
            sequence_number=packet.sequence_number + 1,
            latitude=packet.latitude + (centre_lat - packet.latitude) * 0.1,
            longitude=packet.longitude + (centre_lon - packet.longitude) * 0.1,
            timestamp=packet.timestamp + timedelta(seconds=1),
        )
        now = now + timedelta(seconds=1)
        assessment = engine.assess(packet, now=now)
    assert assessment.eligible
    return manager.add_or_update(assessment, now)


def test_red_priority_before_yellow(config, packet_factory):
    now = datetime.now(timezone.utc)
    manager, engine = PriorityManager(999), GPSEngine(config)
    add(manager, engine, packet_factory(priority=PatientPriority.YELLOW, ambulance_id="AMB-002", trip_id="Y"), now)
    add(manager, engine, packet_factory(priority=PatientPriority.RED, ambulance_id="AMB-001", trip_id="R"), now)
    assert manager.ordered(now)[0].trip_id == "R"


def test_yellow_priority_before_green(config, packet_factory):
    now = datetime.now(timezone.utc)
    manager, engine = PriorityManager(999), GPSEngine(config)
    add(manager, engine, packet_factory(priority=PatientPriority.GREEN, ambulance_id="AMB-002", trip_id="G"), now)
    add(manager, engine, packet_factory(priority=PatientPriority.YELLOW, ambulance_id="AMB-001", trip_id="Y"), now)
    assert manager.ordered(now)[0].trip_id == "Y"


def test_lower_eta_tie_breaker(config, packet_factory):
    now = datetime.now(timezone.utc)
    manager, engine = PriorityManager(999), GPSEngine(config)
    add(manager, engine, packet_factory(distance=200, speed=10, ambulance_id="AMB-001", trip_id="SLOW"), now)
    add(manager, engine, packet_factory(distance=100, speed=10, ambulance_id="AMB-002", trip_id="FAST"), now)
    assert manager.ordered(now)[0].trip_id == "FAST"


def test_waiting_time_tie_breaker(config, packet_factory):
    now = datetime.now(timezone.utc)
    manager, engine = PriorityManager(999), GPSEngine(config)
    older_time = now - timedelta(seconds=5)
    older = add(manager, engine, packet_factory(ambulance_id="AMB-002", trip_id="OLDER", timestamp=older_time), older_time)
    newer = add(manager, engine, packet_factory(ambulance_id="AMB-001", trip_id="NEWER"), now)
    older.eta_seconds = newer.eta_seconds = 10
    assert manager.ordered(now)[0].trip_id == "OLDER"


def test_waiting_time_protection_prevents_starvation(config, packet_factory):
    now = datetime.now(timezone.utc)
    manager, engine = PriorityManager(10), GPSEngine(config)
    older_time = now - timedelta(seconds=25)
    add(manager, engine, packet_factory(priority=PatientPriority.GREEN, ambulance_id="AMB-002", trip_id="OLD", timestamp=older_time), older_time)
    add(manager, engine, packet_factory(priority=PatientPriority.RED, ambulance_id="AMB-001", trip_id="NEW"), now)
    assert manager.ordered(now)[0].trip_id == "OLD"


def test_two_simultaneous_ambulances_are_deterministic(config, packet_factory):
    now = datetime.now(timezone.utc)
    manager, engine = PriorityManager(999), GPSEngine(config)
    add(manager, engine, packet_factory(ambulance_id="AMB-002", trip_id="B"), now)
    add(manager, engine, packet_factory(ambulance_id="AMB-001", trip_id="A"), now)
    for request in manager.ordered(now):
        request.eta_seconds = 10
        request.first_requested_at = now
    assert [request.ambulance_id for request in manager.ordered(now)] == ["AMB-001", "AMB-002"]
