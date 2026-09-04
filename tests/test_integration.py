from datetime import datetime, timedelta, timezone

import pytest

from raspberry_pi_app.core.coordinator import LifeLaneCoordinator
from raspberry_pi_app.core.models import Approach, PatientPriority
from raspberry_pi_app.core.signal_states import PreemptionState, SignalColour
from raspberry_pi_app.simulator.ambulance_factory import create_simulated_ambulance


def drive_simulation(config, side):
    events = []
    coordinator = LifeLaneCoordinator(config, event_callback=lambda kind, message: events.append((kind, message)))
    simulation = create_simulated_ambulance(config, side, speed_mps=15, packet_delay_seconds=1)
    now = datetime.now(timezone.utc)
    signal_history = []
    for step in range(70):
        stamp = now + timedelta(seconds=step)
        packet = simulation.next_packet(stamp)
        if packet:
            coordinator.process_packet(packet, stamp)
        coordinator.tick(1, stamp)
        signal_history.append(dict(coordinator.controller.signals))
    return coordinator, events, signal_history


@pytest.mark.parametrize("side", list(Approach))
def test_simulated_ambulance_each_side_recovers(config, side):
    coordinator, events, signal_history = drive_simulation(config, side)
    assert any(kind == "APPROACH_DETECTED" and side.value.title() in message for kind, message in events)
    assert any(signals[side] is SignalColour.GREEN for signals in signal_history)
    assert any(kind == "AMBULANCE_CROSSED" for kind, _ in events)
    assert coordinator.controller.state is PreemptionState.NORMAL
    assert any(kind == "NORMAL_RESTORED" for kind, _ in events)
    for signals in signal_history:
        ns = any(signals[s] is SignalColour.GREEN for s in (Approach.NORTH, Approach.SOUTH))
        ew = any(signals[s] is SignalColour.GREEN for s in (Approach.EAST, Approach.WEST))
        assert not (ns and ew)


def test_gps_loss_during_ambulance_green_warns_and_times_out(config, packet_factory):
    events = []
    coordinator = LifeLaneCoordinator(config, event_callback=lambda kind, msg: events.append((kind, msg)))
    start = datetime.now(timezone.utc)
    coordinator.process_packet(packet_factory(distance=100, timestamp=start), start)
    for second in range(1, 5):
        coordinator.tick(1, start + timedelta(seconds=second))
    assert coordinator.controller.state in {PreemptionState.AMBULANCE_GREEN, PreemptionState.PASSAGE_MONITORING}
    coordinator.tick(2, start + timedelta(seconds=7))
    assert any(kind == "GPS_CONNECTION_LOST" for kind, _ in events)
    for second in range(8, 35):
        coordinator.tick(1, start + timedelta(seconds=second))
    assert coordinator.controller.state is PreemptionState.NORMAL
    assert any("Maximum ambulance green" in message for _, message in events)


def test_two_conflicting_ambulances_served_without_reversal(config, packet_factory):
    coordinator = LifeLaneCoordinator(config)
    now = datetime.now(timezone.utc)
    north = packet_factory(Approach.NORTH, distance=100, ambulance_id="AMB-001", trip_id="N", priority=PatientPriority.YELLOW, timestamp=now)
    east = packet_factory(Approach.EAST, distance=100, ambulance_id="AMB-002", trip_id="E", priority=PatientPriority.RED, timestamp=now)
    coordinator.process_packet(north, now)
    coordinator.process_packet(east, now)
    assert coordinator.controller.target_trip_id == "N"  # already-selected request cannot be reversed
    assert len(coordinator.priority) == 2
