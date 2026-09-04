"""LifeLane native PySide6 main window."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..communication.mqtt_client import MQTTClient
from ..core.config import JunctionConfig
from ..core.coordinator import LifeLaneCoordinator
from ..core.models import Approach, PatientPriority, TelemetryPacket
from ..database.repository import Repository
from ..simulator.ambulance_factory import create_simulated_ambulance
from ..simulator.gps_simulator import SimulatedAmbulance
from .event_log_panel import EventLogPanel
from .information_panel import InformationPanel
from .junction_scene import JunctionScene, ResponsiveGraphicsView
from .priority_queue_panel import PriorityQueuePanel

LOGGER = logging.getLogger("lifelane.ui")


class MQTTBridge(QObject):
    packet = Signal(object)
    cancel = Signal(str)
    state = Signal(str)
    error = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, config: JunctionConfig, repository: Repository) -> None:
        super().__init__()
        self.config = config
        self.repository = repository
        self.setWindowTitle(f"LifeLane — {config.junction['name']}")
        self.resize(1280, 800)
        self.setMinimumSize(960, 640)

        icon_path = Path(__file__).resolve().parents[1] / "resources" / "icons" / "lifelane.ico"
        if not icon_path.exists():
            icon_path = Path(__file__).resolve().parents[1] / "resources" / "icons" / "lifelane.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.mqtt: MQTTClient | None = None
        self.bridge = MQTTBridge()
        self.bridge.packet.connect(self.process_packet)
        self.bridge.cancel.connect(self.cancel_trip)
        self.bridge.state.connect(self._mqtt_state)
        self.bridge.error.connect(lambda message: self._on_event("MQTT_ERROR", message))
        self.simulations: list[SimulatedAmbulance] = []
        self.simulation_elapsed: dict[str, float] = {}
        self.status_elapsed = 0.0

        self.event_panel = EventLogPanel()
        self.info_panel = InformationPanel()
        self.queue_panel = PriorityQueuePanel()
        self.coordinator = LifeLaneCoordinator(config, repository, self._on_event)
        self.scene = JunctionScene(
            float(config.detection["activation_radius_metres"]),
            float(config.detection["exit_radius_metres"]),
        )
        self.view = ResponsiveGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints() | QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._build_ui()
        self._apply_style()
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._on_event("SAFE_INITIALIZATION", "Application started with all four approaches red")

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 10, 12, 12)
        title_row = QHBoxLayout()
        title = QLabel("LifeLane")
        title.setObjectName("title")
        subtitle = QLabel("Smart Ambulance Traffic Signal Preemption Simulator")
        subtitle.setObjectName("subtitle")
        title_row.addWidget(title)
        title_row.addWidget(subtitle)
        title_row.addStretch()
        warning = QLabel("SIMULATION — NOT APPROVED ROAD TIMINGS")
        warning.setObjectName("warning")
        title_row.addWidget(warning)
        root_layout.addLayout(title_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.view, 1)
        left_layout.addWidget(self._control_panel())
        splitter.addWidget(left)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.addWidget(self.info_panel)
        right_layout.addWidget(self.queue_panel)
        right_layout.addWidget(self.event_panel, 1)
        right_scroll.setWidget(right)
        splitter.addWidget(right_scroll)
        splitter.setSizes([760, 500])
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _control_panel(self) -> QGroupBox:
        box = QGroupBox("Software controls")
        outer = QVBoxLayout(box)
        row1 = QHBoxLayout()
        controls = [
            ("Start normal cycle", self.coordinator.controller.start),
            ("Pause cycle", self.coordinator.controller.pause),
            ("Reset simulator", self.reset_simulator),
            ("Live mobile GPS", self.enable_live_mode),
            ("Built-in simulation", self.enable_simulation_mode),
            ("GPS loss", self.simulate_gps_loss),
            ("Cancel selected", self.cancel_selected),
            ("Clear event log", self.event_panel.clear),
        ]
        for text, callback in controls:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row1.addWidget(button)
        outer.addLayout(row1)

        row2 = QHBoxLayout()
        for side in Approach:
            button = QPushButton(f"Simulate {side.value.title()}")
            button.clicked.connect(lambda _checked=False, selected=side: self.start_simulation(selected))
            row2.addWidget(button)
        second = QPushButton("Add second ambulance")
        second.clicked.connect(self.add_second_ambulance)
        row2.addWidget(second)
        outer.addLayout(row2)

        settings = QHBoxLayout()
        self.side_combo = QComboBox()
        self.side_combo.addItems([side.value for side in Approach])
        self.priority_combo = QComboBox()
        self.priority_combo.addItems([priority.value for priority in PatientPriority])
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.5, 35.0)
        self.speed_spin.setValue(float(self.config.simulation["ambulance_speed_mps"]))
        self.speed_spin.setSuffix(" m/s")
        self.accuracy_spin = QDoubleSpinBox()
        self.accuracy_spin.setRange(1, 80)
        self.accuracy_spin.setValue(float(self.config.simulation["gps_accuracy_metres"]))
        self.accuracy_spin.setSuffix(" m")
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.5, 5.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(float(self.config.simulation["packet_delay_seconds"]))
        self.delay_spin.setSuffix(" s")
        for label, widget in [
            ("Starting side", self.side_combo), ("Priority", self.priority_combo),
            ("Speed", self.speed_spin), ("GPS accuracy", self.accuracy_spin),
            ("Packet delay", self.delay_spin),
        ]:
            settings.addWidget(QLabel(label))
            settings.addWidget(widget)
        settings.addStretch()
        outer.addLayout(settings)
        return box

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#0f172a; color:#cbd5e1; font-size:12px; }
            QLabel#title { color:#38bdf8; font-size:25px; font-weight:700; }
            QLabel#subtitle { color:#f8fafc; font-size:15px; font-weight:600; }
            QLabel#warning { color:#fbbf24; font-weight:700; }
            QGroupBox { border:1px solid #334155; border-radius:7px; margin-top:8px; padding-top:8px; font-weight:600; }
            QGroupBox::title { subcontrol-origin:margin; left:9px; padding:0 4px; color:#7dd3fc; }
            QPushButton { background:#1e3a5f; color:#f8fafc; border:1px solid #2563eb; border-radius:5px; padding:6px 8px; }
            QPushButton:hover { background:#1d4ed8; }
            QComboBox, QDoubleSpinBox { background:#1e293b; border:1px solid #475569; border-radius:4px; padding:4px; }
            QPlainTextEdit, QTableWidget { background:#0b1220; border:1px solid #334155; gridline-color:#334155; }
            QHeaderView::section { background:#1e293b; color:#e2e8f0; padding:4px; border:0; }
            QScrollArea { border:0; }
        """)

    def start_simulation(self, side: Approach | None = None, ambulance_id: str | None = None) -> None:
        selected_side = side or Approach(self.side_combo.currentText())
        simulator = create_simulated_ambulance(
            self.config,
            selected_side,
            ambulance_id=ambulance_id,
            priority=PatientPriority(self.priority_combo.currentText()),
            speed_mps=self.speed_spin.value(),
            accuracy_metres=self.accuracy_spin.value(),
            packet_delay_seconds=self.delay_spin.value(),
        )
        self.simulations.append(simulator)
        self.simulation_elapsed[simulator.trip_id] = simulator.packet_delay_seconds
        self._on_event("SIMULATION_STARTED", f"{simulator.ambulance_id} from {selected_side.value}")

    def add_second_ambulance(self) -> None:
        current = Approach(self.side_combo.currentText())
        opposite = {
            Approach.NORTH: Approach.EAST,
            Approach.EAST: Approach.SOUTH,
            Approach.SOUTH: Approach.WEST,
            Approach.WEST: Approach.NORTH,
        }[current]
        self.start_simulation(opposite, "SIM-SECOND")

    def process_packet(self, packet: TelemetryPacket) -> None:
        result = self.coordinator.process_packet(packet)
        self.info_panel.update_assessment(result)
        if result.valid:
            self.scene.update_ambulance(result)

    def enable_live_mode(self) -> None:
        if self.mqtt is not None:
            return
        self.mqtt = MQTTClient(
            self.config,
            self.bridge.packet.emit,
            self.bridge.cancel.emit,
            self.bridge.state.emit,
            self.bridge.error.emit,
        )
        self.mqtt.start()
        self._on_event("MODE_CHANGED", "Live mobile GPS mode enabled")

    def enable_simulation_mode(self) -> None:
        if self.mqtt:
            self.mqtt.stop()
            self.mqtt = None
        self._mqtt_state("DISCONNECTED (SIMULATION)")
        self._on_event("MODE_CHANGED", "Built-in simulation mode enabled")

    def simulate_gps_loss(self) -> None:
        active = next((simulation for simulation in reversed(self.simulations) if not simulation.finished), None)
        if active:
            active.gps_enabled = False
            self._on_event("GPS_CONNECTION_LOST", f"Simulated GPS loss for {active.trip_id}")
        else:
            self._on_event("GPS_LOSS_IGNORED", "No active simulated ambulance")

    def cancel_selected(self) -> None:
        trip_id = self.coordinator.controller.target_trip_id
        if not trip_id:
            requests = self.coordinator.priority.ordered()
            trip_id = requests[0].trip_id if requests else None
        if trip_id:
            self.cancel_trip(trip_id)

    def cancel_trip(self, trip_id: str) -> None:
        self.coordinator.cancel(trip_id)
        if trip_id in self.scene.ambulances:
            self.scene.ambulances[trip_id].setVisible(False)
        for simulation in self.simulations:
            if simulation.trip_id == trip_id:
                simulation.active = False

    def reset_simulator(self) -> None:
        if self.coordinator.controller.controlled_reset_required:
            answer = QMessageBox.question(self, "Controlled reset", "Reset the fail-safe latch and initialize all signals red?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.simulations.clear()
        self.simulation_elapsed.clear()
        self.scene.clear_ambulances()
        self.coordinator.reset()
        self._refresh_panels()

    def _tick(self) -> None:
        step = self.timer.interval() / 1000.0
        now = datetime.now(timezone.utc)
        for simulation in list(self.simulations):
            self.simulation_elapsed[simulation.trip_id] = self.simulation_elapsed.get(simulation.trip_id, 0) + step
            if self.simulation_elapsed[simulation.trip_id] >= simulation.packet_delay_seconds:
                self.simulation_elapsed[simulation.trip_id] = 0.0
                packet = simulation.next_packet(now)
                if packet:
                    self.process_packet(packet)
            if simulation.finished:
                self.simulations.remove(simulation)
        self.coordinator.tick(step, now)
        self.status_elapsed += step
        if self.mqtt and self.status_elapsed >= 1.0:
            self.status_elapsed = 0.0
            selected_request = self.coordinator.priority.get(self.coordinator.controller.target_trip_id or "")
            self.mqtt.publish_status({
                "online": True,
                "preemptionState": self.coordinator.controller.state.value,
                "signalState": ",".join(
                    f"{side.value}:{colour.value}" for side, colour in self.coordinator.controller.signals.items()
                ),
                "selectedAmbulance": selected_request.ambulance_id if selected_request else "",
                "requestStatus": selected_request.status.value if selected_request else "NONE",
            })
        self.scene.update_signals(self.coordinator.controller.signals)
        self._refresh_panels()

    def _refresh_panels(self) -> None:
        ordered = self.coordinator.priority.ordered()
        self.info_panel.update_controller(self.coordinator.controller, len(ordered))
        self.queue_panel.update_requests(ordered)

    def _mqtt_state(self, state: str) -> None:
        self.info_panel.set_mqtt_state(state)
        self._on_event("MQTT_STATE", state)

    def _on_event(self, event_type: str, message: str) -> None:
        LOGGER.info("%s %s", event_type, message)
        self.event_panel.append_event(event_type, message)
        if event_type == "GPS_CONNECTION_LOST":
            self.info_panel.values["gps"].setText("LOST — SAFE TIMEOUT ACTIVE")
        if self.mqtt and event_type not in {"GPS_PACKET", "NORMAL_PHASE"}:
            self.mqtt.publish_event(event_type, message)
            if event_type in {"REQUEST_ACCEPTED", "AMBULANCE_SELECTED"}:
                trip_id = self.coordinator.controller.target_trip_id
                request = self.coordinator.priority.get(trip_id or "")
                if request:
                    self.mqtt.publish_request(request.ambulance_id, request.trip_id, request.status.value)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.mqtt:
            self.mqtt.stop()
        self.repository.connection.close()
        super().closeEvent(event)
