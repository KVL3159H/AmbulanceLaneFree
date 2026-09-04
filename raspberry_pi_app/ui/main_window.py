"""LifeLane native PySide6 traffic-control-room application shell."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import yaml
from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..communication.mqtt_client import MQTTClient
from ..core.config import JunctionConfig
from ..core.coordinator import LifeLaneCoordinator
from ..core.models import Approach, GPSAssessment, PatientPriority, TelemetryPacket
from ..core.signal_states import NormalPhase, PreemptionState
from ..database.repository import Repository
from ..simulator.ambulance_factory import create_simulated_ambulance
from ..simulator.gps_simulator import SimulatedAmbulance
from .components import (
    ConfirmationDialog,
    ConnectionIndicator,
    DangerButton,
    PrimaryButton,
    SecondaryButton,
    SectionCard,
    StatusBadge,
    ToastNotification,
)
from .event_log_panel import EventLogPanel
from .information_panel import ActiveEmergencyCard, CurrentSignalCard
from .junction_scene import JunctionScene, ResponsiveGraphicsView
from .pages import EmergencyQueuePage, SettingsPage, SystemHealthPage, TripHistoryPage
from .priority_queue_panel import PriorityQueuePanel
from .theme import Color, Space, application_font, icon, load_stylesheet

LOGGER = logging.getLogger("lifelane.ui")


class MQTTBridge(QObject):
    packet = Signal(object)
    cancel = Signal(str)
    state = Signal(str)
    error = Signal(str)
    ambulance_status = Signal(str, bool)


class MainWindow(QMainWindow):
    PAGE_TITLES = ["Live Junction", "Emergency Queue", "Trip History", "System Health", "Settings"]

    def __init__(self, config: JunctionConfig, repository: Repository) -> None:
        super().__init__()
        self.config = config
        self.repository = repository
        from PySide6.QtWidgets import QApplication
        QApplication.instance().setFont(application_font())
        self.setWindowTitle(f"LifeLane — {config.junction['name']}")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        app_icon = icon("app-icon")
        if not app_icon.isNull(): self.setWindowIcon(app_icon)

        self.mqtt: MQTTClient | None = None
        self.mqtt_state = "DISCONNECTED"
        self.ambulance_states: dict[str, bool] = {}
        self.simulations: list[SimulatedAmbulance] = []
        self.simulation_elapsed: dict[str, float] = {}
        self.status_elapsed = 0.0
        self.health_elapsed = 0.0
        self.started_monotonic = time.monotonic()
        self.packet_times: list[datetime] = []
        self.last_packet_at: datetime | None = None
        self.latest_assessment: GPSAssessment | None = None
        self._displayed_trip_id: str | None = None

        self.bridge = MQTTBridge()
        self.bridge.packet.connect(self.process_packet)
        self.bridge.cancel.connect(self.cancel_trip)
        self.bridge.state.connect(self._mqtt_state)
        self.bridge.error.connect(lambda message: self._on_event("MQTT_ERROR", message))
        self.bridge.ambulance_status.connect(self._on_ambulance_status)

        self.coordinator = LifeLaneCoordinator(config, repository, self._on_event)
        self.scene = JunctionScene(float(config.detection["activation_radius_metres"]), float(config.detection["exit_radius_metres"]))
        self.view = ResponsiveGraphicsView(self.scene)
        self.event_panel = EventLogPanel()
        self.signal_card = CurrentSignalCard()
        self.emergency_card = ActiveEmergencyCard()
        self.queue_panel = PriorityQueuePanel()
        self.queue_page = EmergencyQueuePage(repository)
        self.history_page = TripHistoryPage(repository)
        self.health_page = SystemHealthPage(repository)
        self.settings_page = SettingsPage(config)

        self._build_ui()
        self.setStyleSheet(load_stylesheet())
        self._connect_page_actions()
        self.toast = ToastNotification(self)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        self._update_clock()
        self._on_event("SAFE_INITIALIZATION", "Application started with all four approaches red")
        self.enable_live_mode()

    def _build_ui(self) -> None:
        root = QWidget(); root.setObjectName("AppRoot")
        shell = QHBoxLayout(root); shell.setContentsMargins(0, 0, 0, 0); shell.setSpacing(0)
        shell.addWidget(self._navigation_rail())
        body = QWidget(); body_layout = QVBoxLayout(body); body_layout.setContentsMargins(0, 0, 0, 0); body_layout.setSpacing(0)
        body_layout.addWidget(self._top_bar())
        self.page_stack = QStackedWidget(); self.page_stack.setObjectName("PageStack")
        self.page_stack.addWidget(self._live_page())
        self.page_stack.addWidget(self.queue_page)
        self.page_stack.addWidget(self.history_page)
        self.page_stack.addWidget(self.health_page)
        self.page_stack.addWidget(self.settings_page)
        body_layout.addWidget(self.page_stack, 1)
        shell.addWidget(body, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Software simulation · No physical traffic-light outputs", 0)

    def _navigation_rail(self) -> QWidget:
        rail = QWidget(); rail.setObjectName("NavigationRail"); rail.setFixedWidth(188)
        layout = QVBoxLayout(rail); layout.setContentsMargins(12, 18, 12, 16); layout.setSpacing(8)
        brand = QHBoxLayout(); brand.setSpacing(9)
        logo = QLabel(); logo.setPixmap(icon("app-icon").pixmap(42, 42)); logo.setToolTip("LifeLane brand mark")
        brand_text = QVBoxLayout(); brand_text.setSpacing(0)
        product = QLabel("LifeLane"); product.setObjectName("ProductName")
        product_subtitle = QLabel("Emergency Mobility\nIntelligence"); product_subtitle.setObjectName("ProductSubtitle")
        brand_text.addWidget(product); brand_text.addWidget(product_subtitle)
        brand.addWidget(logo); brand.addLayout(brand_text, 1); layout.addLayout(brand); layout.addSpacing(20)
        self.nav_group = QButtonGroup(self); self.nav_group.setExclusive(True); self.nav_buttons: list[QPushButton] = []
        nav_items = [("Live Junction", "junction"), ("Emergency Queue", "queue"), ("Trip History", "history"), ("System Health", "health"), ("Settings", "settings")]
        for index, (label, icon_name) in enumerate(nav_items):
            button = QPushButton(label); button.setCheckable(True); button.setProperty("nav", True); button.setIcon(icon(icon_name)); button.setIconSize(QSize(19, 19))
            button.clicked.connect(lambda _checked=False, page=index: self.show_page(page))
            self.nav_group.addButton(button, index); self.nav_buttons.append(button); layout.addWidget(button)
        self.nav_buttons[0].setChecked(True)
        layout.addStretch()
        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine); separator.setStyleSheet(f"color:{Color.BORDER};"); layout.addWidget(separator)
        simulation = QLabel("SOFTWARE SIMULATION")
        simulation.setObjectName("SimulationMark"); simulation.setAlignment(Qt.AlignmentFlag.AlignCenter); simulation.setToolTip("Demonstration only. No GPIO or physical traffic-light control.")
        layout.addWidget(simulation)
        version = QLabel("LifeLane prototype · v1.0"); version.setObjectName("Muted"); version.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version)
        return rail

    def _top_bar(self) -> QWidget:
        bar = QWidget(); bar.setObjectName("TopBar"); bar.setFixedHeight(76)
        layout = QHBoxLayout(bar); layout.setContentsMargins(24, 10, 20, 10); layout.setSpacing(10)
        titles = QVBoxLayout(); titles.setSpacing(1)
        self.page_title = QLabel("Live Junction"); self.page_title.setObjectName("PageTitle")
        self.page_context = QLabel(f"{self.config.junction['name']}  ·  {self.config.junction['id']}"); self.page_context.setObjectName("PageContext")
        titles.addWidget(self.page_title); titles.addWidget(self.page_context); layout.addLayout(titles); layout.addStretch()
        self.clock = QLabel(); self.clock.setObjectName("Clock"); self.clock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); layout.addWidget(self.clock)
        self.mqtt_badge = ConnectionIndicator("MQTT  Disconnected", "critical")
        self.gps_badge = ConnectionIndicator("GPS  No data", "warning")
        self.system_badge = ConnectionIndicator("System  Healthy", "success")
        for badge in (self.mqtt_badge, self.gps_badge, self.system_badge): layout.addWidget(badge)
        fullscreen = QPushButton(); fullscreen.setIcon(icon("fullscreen")); fullscreen.setIconSize(QSize(20, 20)); fullscreen.setFixedSize(40, 40)
        fullscreen.setToolTip("Toggle full screen (F11)"); fullscreen.setAccessibleName("Toggle full screen"); fullscreen.clicked.connect(self.toggle_fullscreen); layout.addWidget(fullscreen)
        return bar

    def _live_page(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(20, 16, 20, 16); layout.setSpacing(12)
        warning = QFrame(); warning.setObjectName("WarningBanner")
        warning_layout = QHBoxLayout(warning); warning_layout.setContentsMargins(12, 7, 12, 7)
        warning_title = QLabel("Simulation environment")
        warning_title.setStyleSheet(f"color:{Color.AMBER}; font-weight:600;")
        warning_text = QLabel("Timings are for demonstration only. No physical road signals are controlled."); warning_text.setObjectName("Supporting")
        warning_layout.addWidget(warning_title); warning_layout.addWidget(warning_text); warning_layout.addStretch(); layout.addWidget(warning)
        splitter = QSplitter(Qt.Orientation.Horizontal); splitter.setChildrenCollapsible(False)
        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.setContentsMargins(0, 0, 4, 0); left_layout.setSpacing(12)
        canvas = SectionCard()
        canvas_header = QHBoxLayout(); heading = QLabel("Live junction map"); heading.setObjectName("CardTitle")
        map_status = StatusBadge("Vector simulation", "info", "GPS coordinates are projected onto a software-only junction view")
        canvas_header.addWidget(heading); canvas_header.addStretch(); canvas_header.addWidget(map_status)
        canvas.body.addLayout(canvas_header); canvas.body.addWidget(self.view, 1); left_layout.addWidget(canvas, 1); left_layout.addWidget(self._simulation_controls())
        splitter.addWidget(left)
        right_scroll = QScrollArea(); right_scroll.setObjectName("PageScroll"); right_scroll.setWidgetResizable(True); right_scroll.setMinimumWidth(340)
        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.setContentsMargins(4, 0, 0, 0); right_layout.setSpacing(12)
        right_layout.addWidget(self.signal_card); right_layout.addWidget(self.emergency_card)
        queue_card = SectionCard("Emergency queue", "Medical priority, ETA and waiting time determine automatic ordering.")
        queue_card.body.addWidget(self.queue_panel); right_layout.addWidget(queue_card, 1)
        right_scroll.setWidget(right); splitter.addWidget(right_scroll); splitter.setStretchFactor(0, 65); splitter.setStretchFactor(1, 35); splitter.setSizes([760, 400])
        layout.addWidget(splitter, 1); layout.addWidget(self.event_panel)
        return page

    def _simulation_controls(self) -> QWidget:
        card = SectionCard("Simulation controls", "All actions operate the software model only.")
        top = QHBoxLayout(); top.setSpacing(Space.SM)
        self.start_button = PrimaryButton("Start normal cycle"); self.start_button.clicked.connect(self.coordinator.controller.start)
        pause = SecondaryButton("Pause cycle"); pause.clicked.connect(self.coordinator.controller.pause)
        reset = SecondaryButton("Controlled reset"); reset.clicked.connect(self.reset_simulator)
        live = SecondaryButton("Live mobile GPS"); live.clicked.connect(self.enable_live_mode)
        built_in = SecondaryButton("Built-in simulation"); built_in.clicked.connect(self.enable_simulation_mode)
        compact_labels = ("Start cycle", "Pause", "Safe reset", "Live GPS", "Simulation")
        tooltips = (
            "Start the normal traffic-signal state machine",
            "Pause the software signal cycle safely",
            "Reset to the all-red safe initialization state",
            "Receive live mobile GPS packets over MQTT",
            "Use internally generated, clearly marked simulated ambulances",
        )
        for button, label, tooltip in zip((self.start_button, pause, reset, live, built_in), compact_labels, tooltips):
            button.setText(label); button.setToolTip(tooltip); top.addWidget(button, 1)
        card.body.addLayout(top)
        self.last_simulation_side = Approach.NORTH
        simulate = PrimaryButton("Add simulated ambulance"); simulate.clicked.connect(self.open_simulation_dialog)
        second = SecondaryButton("Add second"); second.clicked.connect(self.add_second_ambulance)
        gps_loss = DangerButton("Simulate GPS loss"); gps_loss.clicked.connect(self.simulate_gps_loss)
        actions = QHBoxLayout(); actions.setSpacing(Space.SM)
        actions.addWidget(simulate, 2); actions.addWidget(second, 1); actions.addWidget(gps_loss, 1)
        card.body.addLayout(actions)
        return card

    def open_simulation_dialog(self) -> None:
        dialog = QDialog(self); dialog.setWindowTitle("Add simulated ambulance"); dialog.setMinimumWidth(430)
        root = QVBoxLayout(dialog); root.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL); root.setSpacing(Space.LG)
        heading = QLabel("Simulated ambulance setup"); heading.setObjectName("SectionTitle"); root.addWidget(heading)
        detail = QLabel("Generated telemetry is visibly marked SIMULATED and only operates the software model.")
        detail.setObjectName("Supporting"); detail.setWordWrap(True); root.addWidget(detail)
        form = QFormLayout(); form.setSpacing(Space.MD)
        side = QComboBox(); side.addItems([value.value.title() for value in Approach]); side.setCurrentText(self.last_simulation_side.value.title())
        priority = QComboBox(); priority.addItems(["Critical", "Serious", "Stable"])
        speed = QDoubleSpinBox(); speed.setRange(0.5, 35); speed.setValue(float(self.config.simulation["ambulance_speed_mps"])); speed.setSuffix(" m/s")
        accuracy = QDoubleSpinBox(); accuracy.setRange(1, 80); accuracy.setValue(float(self.config.simulation["gps_accuracy_metres"])); accuracy.setSuffix(" m")
        delay = QDoubleSpinBox(); delay.setRange(0.5, 5); delay.setSingleStep(0.5); delay.setValue(float(self.config.simulation["packet_delay_seconds"])); delay.setSuffix(" s")
        for label, field in (("Starting approach", side), ("Medical priority", priority), ("Travel speed", speed), ("GPS accuracy", accuracy), ("Packet interval", delay)):
            form.addRow(label, field)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        add = PrimaryButton("Add ambulance"); add.clicked.connect(dialog.accept); buttons.addButton(add, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(dialog.reject); root.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_side = Approach(side.currentText().upper()); self.last_simulation_side = selected_side
        selected_priority = {"Critical": PatientPriority.RED, "Serious": PatientPriority.YELLOW, "Stable": PatientPriority.GREEN}[priority.currentText()]
        self.start_simulation(selected_side, priority=selected_priority, speed_mps=speed.value(), accuracy_metres=accuracy.value(), packet_delay_seconds=delay.value())

    def _connect_page_actions(self) -> None:
        self.queue_page.cancel_requested.connect(lambda trip: self.cancel_trip(trip, "Cancelled by operator"))
        self.queue_page.hold_requested.connect(self.hold_request)
        self.queue_page.restore_requested.connect(self.restore_request)
        self.settings_page.settings_applied.connect(self.apply_settings)

    def show_page(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index); self.page_title.setText(self.PAGE_TITLES[index]); self.nav_buttons[index].setChecked(True)
        if index == 2: self.history_page.refresh()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen(): self.showNormal(); self.showMaximized()
        else: self.showFullScreen()

    def start_simulation(self, side: Approach | None = None, ambulance_id: str | None = None,
                         priority: PatientPriority = PatientPriority.RED, speed_mps: float | None = None,
                         accuracy_metres: float | None = None, packet_delay_seconds: float | None = None) -> None:
        selected_side = side or self.last_simulation_side; self.last_simulation_side = selected_side
        simulator = create_simulated_ambulance(
            self.config, selected_side, ambulance_id=ambulance_id, priority=priority,
            speed_mps=speed_mps if speed_mps is not None else float(self.config.simulation["ambulance_speed_mps"]),
            accuracy_metres=accuracy_metres if accuracy_metres is not None else float(self.config.simulation["gps_accuracy_metres"]),
            packet_delay_seconds=packet_delay_seconds if packet_delay_seconds is not None else float(self.config.simulation["packet_delay_seconds"]),
        )
        self.simulations.append(simulator); self.simulation_elapsed[simulator.trip_id] = simulator.packet_delay_seconds
        self._on_event("SIMULATION_STARTED", f"{simulator.ambulance_id} from {selected_side.value}; demo data marked simulated")

    def add_second_ambulance(self) -> None:
        current = self.last_simulation_side
        opposite = {Approach.NORTH: Approach.EAST, Approach.EAST: Approach.SOUTH, Approach.SOUTH: Approach.WEST, Approach.WEST: Approach.NORTH}[current]
        self.start_simulation(opposite, "SIM-SECOND")

    def process_packet(self, packet: TelemetryPacket) -> None:
        result = self.coordinator.process_packet(packet); self.latest_assessment = result
        self.last_packet_at = datetime.now(timezone.utc); self.packet_times.append(self.last_packet_at); self.packet_times = self.packet_times[-20:]
        if result.valid:
            self.scene.update_ambulance(result); self.gps_badge.set_connection("GPS", "Live")
        else:
            self.gps_badge.set_connection("GPS", "Inaccurate")

    def enable_live_mode(self) -> None:
        if self.mqtt is not None: return
        self.mqtt = MQTTClient(self.config, self.bridge.packet.emit, self.bridge.cancel.emit, self.bridge.state.emit,
                               self.bridge.error.emit, self.bridge.ambulance_status.emit)
        self.mqtt.start(); self._on_event("MODE_CHANGED", "Live mobile GPS mode enabled")

    def enable_simulation_mode(self) -> None:
        if self.mqtt:
            self.mqtt.stop(); self.mqtt = None
        self._mqtt_state("DISCONNECTED (SIMULATION)"); self._on_event("MODE_CHANGED", "Built-in simulation mode enabled")

    def simulate_gps_loss(self) -> None:
        active = next((item for item in reversed(self.simulations) if not item.finished), None)
        if active:
            active.gps_enabled = False; self._on_event("GPS_CONNECTION_LOST", f"Simulated GPS loss for {active.trip_id}")
        else:
            self._on_event("GPS_LOSS_IGNORED", "No active simulated ambulance")
            self.toast.show_message("No active simulated ambulance is available for GPS-loss testing.")

    def cancel_selected(self) -> None:
        trip_id = self.queue_panel.selected_trip_id() or self.coordinator.controller.target_trip_id
        if trip_id and ConfirmationDialog.confirm(self, "Cancel request", "Cancel the selected emergency request?", "Cancel request", True): self.cancel_trip(trip_id)

    def cancel_trip(self, trip_id: str, reason: str = "Emergency trip cancelled") -> None:
        self.coordinator.cancel(trip_id, reason); self.scene.hide_ambulance(trip_id)
        for simulation in self.simulations:
            if simulation.trip_id == trip_id: simulation.active = False

    def hold_request(self, trip_id: str) -> None:
        if self.coordinator.priority.hold(trip_id): self._on_event("REQUEST_HELD", f"{trip_id} temporarily held by operator")
        else: self.toast.show_message("The active controller request cannot be held.")

    def restore_request(self, trip_id: str) -> None:
        if self.coordinator.priority.restore(trip_id): self._on_event("REQUEST_RESTORED", f"{trip_id} restored to automatic priority ordering")

    def reset_simulator(self) -> None:
        if self.coordinator.controller.controlled_reset_required and not ConfirmationDialog.confirm(
            self, "Controlled reset", "Reset the fail-safe latch and initialize every approach to red?", "Reset safely", True): return
        self.simulations.clear(); self.simulation_elapsed.clear(); self.scene.clear_ambulances(); self.coordinator.reset(); self.latest_assessment = None
        self.emergency_card.clear_active(); self._refresh_panels()

    def apply_settings(self, values: dict) -> None:
        old_broker = (self.config.mqtt["broker"], int(self.config.mqtt["port"]))
        for compound, value in values.items():
            section, key = compound.split(".", 1); self.config.raw[section][key] = value
        try:
            self.config.source.write_text(yaml.safe_dump(self.config.raw, sort_keys=False), encoding="utf-8")
        except OSError as exc:
            self._on_event("CONFIG_ERROR", f"Settings applied for this session but could not be saved: {exc}")
        self.page_context.setText(f"{self.config.junction['name']}  ·  {self.config.junction['id']}")
        self.setWindowTitle(f"LifeLane — {self.config.junction['name']}")
        self.scene = JunctionScene(float(self.config.detection["activation_radius_metres"]), float(self.config.detection["exit_radius_metres"])); self.view.setScene(self.scene)
        if old_broker != (self.config.mqtt["broker"], int(self.config.mqtt["port"])) and not os.getenv("LIFELANE_MQTT_HOST"):
            if self.mqtt: self.mqtt.stop(); self.mqtt = None
            self.enable_live_mode()
        self._on_event("CONFIG_UPDATED", "Validated junction settings applied")
        self.toast.show_message("Settings validated and applied.")

    def _tick(self) -> None:
        step = self.timer.interval() / 1000.0; now = datetime.now(timezone.utc)
        for simulation in list(self.simulations):
            self.simulation_elapsed[simulation.trip_id] = self.simulation_elapsed.get(simulation.trip_id, 0) + step
            if self.simulation_elapsed[simulation.trip_id] >= simulation.packet_delay_seconds:
                self.simulation_elapsed[simulation.trip_id] = 0.0; packet = simulation.next_packet(now)
                if packet: self.process_packet(packet)
            if simulation.finished: self.simulations.remove(simulation)
        self.coordinator.tick(step, now); self.status_elapsed += step; self.health_elapsed += step
        if self.mqtt and self.status_elapsed >= 1.0:
            self.status_elapsed = 0.0; selected = self.coordinator.priority.get(self.coordinator.controller.target_trip_id or "")
            self.mqtt.publish_status({"online": True, "preemptionState": self.coordinator.controller.state.value,
                "signalState": ",".join(f"{side.value}:{colour.value}" for side, colour in self.coordinator.controller.signals.items()),
                "selectedAmbulance": selected.ambulance_id if selected else "", "requestStatus": selected.status.value if selected else "NONE"})
        self.scene.update_signals(self.coordinator.controller.signals); self._refresh_panels()
        if self.health_elapsed >= 1.0:
            self.health_elapsed = 0.0
            self._refresh_health()
            self.queue_page.refresh_outcomes()

    def _remaining_time(self) -> float | None:
        controller = self.coordinator.controller; timing = self.config.timing
        if not controller.running: return None
        if controller.state is PreemptionState.NORMAL:
            duration = {NormalPhase.NS_GREEN: timing["normal_green_seconds"], NormalPhase.NS_YELLOW: timing["yellow_seconds"],
                        NormalPhase.ALL_RED_BEFORE_EW: timing["all_red_seconds"], NormalPhase.EW_GREEN: timing["normal_green_seconds"],
                        NormalPhase.EW_YELLOW: timing["yellow_seconds"], NormalPhase.ALL_RED_BEFORE_NS: timing["all_red_seconds"]}[controller.normal_phase]
        elif controller.state in {PreemptionState.CLEAR_CURRENT_GREEN, PreemptionState.RECOVERY_YELLOW}: duration = timing["yellow_seconds"]
        elif controller.state in {PreemptionState.ALL_RED_CLEARANCE, PreemptionState.RECOVERY_ALL_RED}: duration = timing["all_red_seconds"]
        elif controller.state is PreemptionState.PREEMPTION_PENDING: duration = controller._pending_minimum_green
        elif controller.state in {PreemptionState.REQUEST_VALIDATION, PreemptionState.AMBULANCE_GREEN}: duration = 0.0
        elif controller.state is PreemptionState.PASSAGE_MONITORING: duration = timing["maximum_ambulance_green_seconds"]
        else: return None
        return max(0.0, float(duration) - controller.elapsed)

    def _refresh_panels(self) -> None:
        ordered = self.coordinator.priority.ordered(); all_requests = self.coordinator.priority.all_requests(); target = self.coordinator.controller.target_trip_id
        target_request = self.coordinator.priority.get(target or "")
        self.signal_card.update_controller(self.coordinator.controller, self._remaining_time(), target_request)
        self.queue_panel.update_requests(ordered, target); self.queue_page.update_requests(all_requests, target); self.scene.set_selected_trip(target)
        active = self.coordinator.latest.get(target) if target else None
        if active is None and ordered:
            active = self.coordinator.latest.get(ordered[0].trip_id)
        if active is None and self.latest_assessment and self.latest_assessment.packet.emergency_active:
            if self.latest_assessment.packet.trip_id not in self.coordinator.completed_trips:
                active = self.latest_assessment
        if active is not None:
            request = self.coordinator.priority.get(active.packet.trip_id)
            self.emergency_card.update_assessment(active, request)
            self._displayed_trip_id = active.packet.trip_id
        elif self._displayed_trip_id is not None:
            self.emergency_card.clear_active(); self._displayed_trip_id = None
    def _refresh_health(self) -> None:
        packet_hz = None
        if len(self.packet_times) >= 2:
            duration = (self.packet_times[-1] - self.packet_times[0]).total_seconds()
            if duration > 0: packet_hz = (len(self.packet_times) - 1) / duration
        device = next((key for key, online in self.ambulance_states.items() if online), "No device")
        self.health_page.refresh(self.mqtt_state, device, self.last_packet_at, packet_hz, time.monotonic() - self.started_monotonic, self.coordinator.controller.state.value)
        if self.last_packet_at and (datetime.now(timezone.utc) - self.last_packet_at).total_seconds() > float(self.config.detection["maximum_packet_age_seconds"]):
            self.gps_badge.set_connection("GPS", "Stale")

    def _mqtt_state(self, state: str) -> None:
        self.mqtt_state = state; display = state.split(" ", 1)[0]; self.mqtt_badge.set_connection("MQTT", display); self._on_event("MQTT_STATE", state)

    def _on_ambulance_status(self, ambulance_id: str, online: bool) -> None:
        if not ambulance_id: return
        self.ambulance_states[ambulance_id] = online
        self._on_event("AMBULANCE_STATUS", f"{ambulance_id} is {'online' if online else 'offline'}")

    def _on_event(self, event_type: str, message: str) -> None:
        LOGGER.info("%s %s", event_type, message); self.event_panel.append_event(event_type, message)
        if event_type == "GPS_CONNECTION_LOST": self.gps_badge.set_connection("GPS", "Lost"); self.emergency_card.show_gps_loss(); self.toast.show_message(message, 6000)
        elif event_type in {"CRITICAL_FAIL_SAFE", "MQTT_ERROR", "CONFIG_ERROR"}: self.toast.show_message(message, 7000)
        elif event_type == "AMBULANCE_SELECTED": self.toast.show_message(message)
        if self.mqtt and event_type not in {"GPS_PACKET", "NORMAL_PHASE"}:
            self.mqtt.publish_event(event_type, message)
            if event_type in {"REQUEST_ACCEPTED", "AMBULANCE_SELECTED"}:
                request = self.coordinator.priority.get(self.coordinator.controller.target_trip_id or "")
                if request: self.mqtt.publish_request(request.ambulance_id, request.trip_id, request.status.value)

    def _update_clock(self) -> None:
        self.clock.setText(datetime.now().astimezone().strftime("%a, %d %b %Y\n%H:%M:%S"))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible(): self.toast.move(max(16, self.width() - self.toast.width() - 24), 82)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop(); self.clock_timer.stop()
        if self.mqtt: self.mqtt.stop()
        self.repository.connection.close(); super().closeEvent(event)
