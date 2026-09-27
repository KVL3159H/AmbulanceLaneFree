from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

pytest.importorskip("PySide6")

from raspberry_pi_app.core.models import Approach
from raspberry_pi_app.database.connection import connect_database
from raspberry_pi_app.database.repository import Repository
from raspberry_pi_app.ui.main_window import MainWindow


def make_window(config, monkeypatch, qtbot):
    monkeypatch.setattr(MainWindow, "enable_live_mode", lambda self: None)
    connection = connect_database(":memory:")
    window = MainWindow(config, Repository(connection, str(config.junction["id"])))
    window.timer.stop()
    qtbot.addWidget(window)
    return window


def test_professional_shell_navigation_and_scaling(config, monkeypatch, qtbot):
    window = make_window(config, monkeypatch, qtbot)
    window.resize(1100, 700)
    window.show()
    qtbot.wait(100)
    assert window.minimumWidth() == 1100
    assert window.minimumHeight() == 700
    assert window.page_stack.count() == 8
    for page in range(8):
        window.show_page(page)
        assert window.page_stack.currentIndex() == page
        assert window.page_title.text() == window.PAGE_TITLES[page]


def test_live_emergency_queue_and_gps_loss_states(config, monkeypatch, qtbot):
    window = make_window(config, monkeypatch, qtbot)
    window.start_simulation(Approach.NORTH)
    simulation = window.simulations[-1]
    simulation.signed_distance_metres = 100
    simulation.advance_after_packet = True
    now = datetime.now(timezone.utc)
    for i in range(4):
        packet = simulation.next_packet(now-timedelta(seconds=3-i))
        assert packet is not None
        window.process_packet(packet)
    window.coordinator.tick(1)
    window._refresh_panels()
    assert not window.emergency_card.content.isHidden()
    assert len(window.coordinator.priority) == 1
    assert window.queue_panel.table.rowCount() == 1
    window.simulate_gps_loss()
    assert window.gps_badge.text().endswith("Lost")


def test_fail_safe_has_explicit_critical_presentation(config, monkeypatch, qtbot):
    window = make_window(config, monkeypatch, qtbot)
    window.coordinator.controller._enter_fail_safe("UI verification")
    window._refresh_panels()
    assert window.signal_card.badge.text() == "Fail-safe active"
    assert window.signal_card.badge.property("tone") == "critical"
    assert "forced red" in window.signal_card.explanation.text()


def test_active_emergency_tracks_controller_selection(config, packet_factory, monkeypatch, qtbot):
    window = make_window(config, monkeypatch, qtbot)
    now = datetime.now(timezone.utc)
    for side, identity, trip in [(Approach.NORTH,"AMB-001","N"),(Approach.EAST,"AMB-002","E")]:
        for i in range(4):
            window.process_packet(packet_factory(side, distance=130-10*i, sequence=i+1, ambulance_id=identity, trip_id=trip, timestamp=now-timedelta(seconds=3-i)))
    window._refresh_panels()
    assert window.coordinator.controller.target_trip_id == "N"
    assert window.emergency_card.rows["ambulance"].value.text() == "AMB-001"
    assert window.signal_card.selected.value.text() == "AMB-001"


def test_rejected_request_is_visible_with_reason(config, packet_factory, monkeypatch, qtbot):
    window = make_window(config, monkeypatch, qtbot)
    window.process_packet(packet_factory(accuracy=80))
    window.queue_page.refresh_outcomes()
    assert window.queue_page.outcomes.rowCount() == 1
    assert window.queue_page.outcomes.item(0, 6).text() == "Rejected"
    assert "accuracy" in window.queue_page.outcomes.item(0, 7).text().lower()


def test_hardware_monitor_never_ticks_local_controller(config, monkeypatch, qtbot):
    import time
    from raspberry_pi_app.core.signal_states import SignalColour
    window = make_window(config, monkeypatch, qtbot)
    class Monitor:
        stopped = False
        def stop(self): self.stopped = True
    monitor = Monitor()
    window.hardware_monitor = monitor
    window.hardware_heartbeat = time.monotonic()
    window.hardware_lamps = {s: SignalColour.RED for s in Approach}
    monkeypatch.setattr(window.coordinator, "tick", lambda *args: pytest.fail("Local controller ran in hardware mode"))
    window.traffic.spawn(Approach.NORTH)
    window._advance_simulation(0.5)
    position = window.traffic.vehicles[0].progress
    window.hardware_heartbeat -= 6
    window._advance_simulation(1)
    assert window.traffic.vehicles[0].progress == position
    window.traffic.running=False
    window._tick()
    assert "unavailable" in window.system_badge.text()
    window.start_simulation(Approach.EAST)
    assert monitor.stopped and window.hardware_monitor is None
    assert "SIMULATION" in window.statusBar().currentMessage()


def test_simulated_gps_clock_uses_simulation_elapsed_time(config, monkeypatch, qtbot):
    window = make_window(config, monkeypatch, qtbot)
    start = window.simulation_clock
    window._advance_simulation(0.5)
    window._advance_simulation(2)
    assert (window.simulation_clock-start).total_seconds() == 2.5


def test_continuous_desktop_ambulance_clears_and_restores(config, monkeypatch, qtbot):
    window=make_window(config,monkeypatch,qtbot)
    window.start_simulation(Approach.NORTH)
    trip=window.simulations[-1].trip_id
    for _ in range(360): window._advance_simulation(.5)
    assert window.coordinator.outcomes.get(trip)=="JUNCTION_CLEARED"
    assert not window.simulations
    report=window.structured_log.trip_report(trip)
    assert report["checks"]["normalRestorationRecorded"]
    assert window.traffic.cleared > 0
    measured=next(row for row in window.structured_log.metrics()["ambulanceMeasurements"] if row["tripId"]==trip)
    assert measured["junctionOccupationSeconds"] > 0
    assert measured["monitoredTravelSeconds"] > measured["junctionOccupationSeconds"]


def test_delayed_simulation_packets_are_rejected_as_stale(config, monkeypatch, qtbot):
    window=make_window(config,monkeypatch,qtbot)
    window.start_simulation(Approach.NORTH)
    window.simulations[-1].network_delay_seconds=8
    for _ in range(24): window._advance_simulation(.5)
    assert window.latest_assessment is not None
    assert not window.latest_assessment.valid
    assert "stale" in window.latest_assessment.reason
    assert len(window.coordinator.priority)==0


def test_stop_finishes_yellow_before_holding_all_red(config,monkeypatch,qtbot):
    from raspberry_pi_app.core.signal_states import SignalColour
    window=make_window(config,monkeypatch,qtbot)
    for _ in range(6): window._advance_simulation(.5)
    assert SignalColour.GREEN in window.coordinator.controller.signals.values()
    window.stop_simulation()
    yellow=False
    for _ in range(60):
        window._advance_simulation(.5)
        yellow |= SignalColour.YELLOW in window.coordinator.controller.signals.values()
        if not window.traffic.running: break
    assert yellow and not window.traffic.running
    assert all(c is SignalColour.RED for c in window.coordinator.controller.signals.values())
