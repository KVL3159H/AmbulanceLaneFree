from __future__ import annotations

import pytest

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
    assert window.page_stack.count() == 5
    for page in range(5):
        window.show_page(page)
        assert window.page_stack.currentIndex() == page
        assert window.page_title.text() == window.PAGE_TITLES[page]


def test_live_emergency_queue_and_gps_loss_states(config, monkeypatch, qtbot):
    window = make_window(config, monkeypatch, qtbot)
    window.start_simulation(Approach.NORTH)
    simulation = window.simulations[-1]
    simulation.signed_distance_metres = 100
    packet = simulation.next_packet()
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
    window.process_packet(packet_factory(Approach.NORTH, distance=100, ambulance_id="AMB-001", trip_id="N"))
    window.process_packet(packet_factory(Approach.EAST, distance=100, ambulance_id="AMB-002", trip_id="E"))
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
