"""LifeLane native PySide6 traffic-control-room application shell."""



from __future__ import annotations



import logging

import os

import time

from datetime import datetime, timedelta, timezone



import yaml

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal

from PySide6.QtGui import QKeySequence, QShortcut

from PySide6.QtWidgets import (

    QButtonGroup,
    QTabWidget,

    QComboBox,

    QDoubleSpinBox,

    QDialog,

    QDialogButtonBox,

    QFormLayout,

    QFrame,

    QHBoxLayout,
    QGridLayout,

    QLabel,

    QMainWindow,

    QPushButton,

    QScrollArea,

    QSplitter,

    QStackedWidget,

    QVBoxLayout,

    QWidget,

)

from ..communication.hardware_bridge import HardwareBridge
from ..communication.mqtt_client import MQTTClient
from ..communication.hardware_monitor import HardwareMonitor

from ..core.config import JunctionConfig
from ..core.event_logger import EventLogger
from .upgrade_pages import MetricsPage, ScenarioPage, LogsPage

from ..core.coordinator import LifeLaneCoordinator

from ..core.models import Approach, GPSAssessment, PatientPriority, TelemetryPacket

from ..core.signal_states import NormalPhase, PreemptionState, SignalColour

from ..database.repository import Repository

from ..simulator.ambulance_factory import create_simulated_ambulance

from ..simulator.gps_simulator import SimulatedAmbulance

from ..simulator.traffic_engine import TrafficEngine, Vehicle

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
from .voice_announcer import VoiceAnnouncer



LOGGER = logging.getLogger("lifelane.ui")





class MQTTBridge(QObject):

    packet = Signal(object)
    hardware = Signal(object)

    cancel = Signal(str)

    state = Signal(str)

    error = Signal(str)

    ambulance_status = Signal(str, bool)
    hardware_status = Signal(bool, str)





class MainWindow(QMainWindow):

    PAGE_TITLES = ["Live Simulation", "Junction Controller", "Ambulances", "Traffic Metrics", "MQTT Monitor", "Scenario Testing", "Event Logs", "Settings"]



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



        self.structured_log = EventLogger()
        self.voice_announcer = VoiceAnnouncer(enabled=True)
        self.mqtt: MQTTClient | None = None

        self.hardware_monitor = None
        self.hil_adapter = None
        self.hardware_heartbeat = None
        self.hardware_lamps = {side:SignalColour.RED for side in Approach}
        self.hardware_acks = {}
        self.hardware_passage_events = set()
        self.mqtt_state = "DISCONNECTED"

        self.ambulance_states: dict[str, bool] = {}

        self.simulations: list[SimulatedAmbulance] = []

        self.simulation_elapsed: dict[str, float] = {}
        self.pending_packets = []
        self.simulated_network_available = True
        self.stop_at_all_red = False
        self.reject_next_simulated_request = False

        self.traffic = TrafficEngine()
        for side in Approach: self.traffic.spawn(side)

        self.simulation_speed = 1.0

        self.traffic_spawn_elapsed = 0.0

        self.last_tick = time.monotonic()
        self.simulation_clock = datetime.now(timezone.utc)

        self.status_elapsed = 0.0

        self.health_elapsed = 0.0

        self.started_monotonic = time.monotonic()

        self.packet_times: list[datetime] = []

        self.last_packet_at: datetime | None = None

        self.latest_assessment: GPSAssessment | None = None

        self._displayed_trip_id: str | None = None



        self.bridge = MQTTBridge()

        self.bridge.packet.connect(self.process_packet)
        self.bridge.hardware.connect(self.receive_hardware)

        self.bridge.cancel.connect(self.cancel_trip)

        self.bridge.state.connect(self._mqtt_state)

        self.bridge.error.connect(lambda message: self._on_event("MQTT_ERROR", message))

        self.bridge.ambulance_status.connect(self._on_ambulance_status)
        self.bridge.hardware_status.connect(self._handle_hardware_status)



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
        self.metrics_page = MetricsPage()
        self.scenario_page = ScenarioPage(config)
        self.logs_page = LogsPage(self.structured_log)
        self.controller_page = QWidget(); controller_layout = QVBoxLayout(self.controller_page)
        self.controller_details = QLabel(); controller_layout.addWidget(self.controller_details)
        self.controller_view = ResponsiveGraphicsView(self.scene)
        controller_layout.addWidget(self.controller_view)
        self.ambulances_page = QTabWidget()
        self.ambulances_page.addTab(self.queue_page, "Emergency queue")
        self.ambulances_page.addTab(self.history_page, "Trip history")



        self._build_ui()

        self.setStyleSheet(load_stylesheet())

        self._connect_page_actions()

        self.toast = ToastNotification(self)

        self.timer = QTimer(self)

        self.timer.setInterval(33)

        self.timer.timeout.connect(self._tick)

        self.timer.start()

        self.clock_timer = QTimer(self)

        self.clock_timer.setInterval(1000)

        self.clock_timer.timeout.connect(self._update_clock)

        self.clock_timer.start()

        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

        self._update_clock()

        self._on_event("SAFE_INITIALIZATION", "Application started with all four approaches red")
        self.hardware_bridge = HardwareBridge(status_callback=self._on_hardware_status_callback)
        self.hardware_bridge.start()
        self.enable_live_mode()



    def _build_ui(self) -> None:

        root = QWidget(); root.setObjectName("AppRoot")

        shell = QHBoxLayout(root); shell.setContentsMargins(0, 0, 0, 0); shell.setSpacing(0)

        shell.addWidget(self._navigation_rail())

        body = QWidget(); body_layout = QVBoxLayout(body); body_layout.setContentsMargins(0, 0, 0, 0); body_layout.setSpacing(0)

        body_layout.addWidget(self._top_bar())

        self.page_stack = QStackedWidget(); self.page_stack.setObjectName("PageStack")

        self.page_stack.addWidget(self._live_page())

        for page in (self.controller_page,self.ambulances_page,self.metrics_page,self.health_page,self.scenario_page,self.logs_page,self.settings_page):
            self.page_stack.addWidget(page)
        body_layout.addWidget(self.page_stack, 1)

        shell.addWidget(body, 1)

        self.setCentralWidget(root)

        self.statusBar().showMessage("Software simulation · No physical traffic-light outputs", 0)



    def _navigation_rail(self) -> QWidget:

        rail = QWidget(); rail.setObjectName("NavigationRail"); rail.setFixedWidth(215)

        layout = QVBoxLayout(rail); layout.setContentsMargins(12, 18, 12, 16); layout.setSpacing(8)

        brand = QHBoxLayout(); brand.setSpacing(9)

        logo = QLabel(); logo.setPixmap(icon("app-icon").pixmap(42, 42)); logo.setToolTip("LifeLane brand mark")

        brand_text = QVBoxLayout(); brand_text.setSpacing(0)

        product = QLabel("LifeLane"); product.setObjectName("ProductName")

        product_subtitle = QLabel("Emergency Mobility\nIntelligence"); product_subtitle.setObjectName("ProductSubtitle")

        brand_text.addWidget(product); brand_text.addWidget(product_subtitle)

        brand.addWidget(logo); brand.addLayout(brand_text, 1); layout.addLayout(brand); layout.addSpacing(20)

        self.nav_group = QButtonGroup(self); self.nav_group.setExclusive(True); self.nav_buttons: list[QPushButton] = []

        nav_items = list(zip(self.PAGE_TITLES,["junction","junction","medical","history","health","settings","history","settings"]))
        for index, (label, icon_name) in enumerate(nav_items):

            button = QPushButton(label); button.setCheckable(True); button.setProperty("nav", True); button.setIcon(icon(icon_name)); button.setIconSize(QSize(19, 19))

            button.clicked.connect(lambda _checked=False, page=index: self.show_page(page))

            self.nav_group.addButton(button, index); self.nav_buttons.append(button); layout.addWidget(button)

        self.nav_buttons[0].setChecked(True)

        layout.addStretch()

        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine); separator.setStyleSheet(f"color:{Color.BORDER};"); layout.addWidget(separator)

        simulation = QLabel("SOFTWARE SIMULATION")
        self.mode_footer = simulation

        simulation.setObjectName("SimulationMark"); simulation.setAlignment(Qt.AlignmentFlag.AlignCenter); simulation.setToolTip("Demonstration only. No GPIO or physical traffic-light control.")

        layout.addWidget(simulation)

        version = QLabel("LifeLane prototype · v1.2"); version.setObjectName("Muted"); version.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version)

        return rail



    def _top_bar(self) -> QWidget:

        bar = QWidget(); bar.setObjectName("TopBar"); bar.setFixedHeight(76)

        layout = QHBoxLayout(bar); layout.setContentsMargins(24, 10, 20, 10); layout.setSpacing(10)

        titles = QVBoxLayout(); titles.setSpacing(1)

        self.page_title = QLabel("Live Simulation"); self.page_title.setObjectName("PageTitle")

        self.page_context = QLabel(f"{self.config.junction['name']}  ·  {self.config.junction['id']}"); self.page_context.setObjectName("PageContext")

        titles.addWidget(self.page_title); titles.addWidget(self.page_context); layout.addLayout(titles); layout.addStretch()

        self.clock = QLabel(); self.clock.setObjectName("Clock"); self.clock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); layout.addWidget(self.clock)

        self.mqtt_badge = ConnectionIndicator("MQTT  Disconnected", "critical")

        self.gps_badge = ConnectionIndicator("GPS  No data", "warning")
        self.hardware_badge = ConnectionIndicator("ESP32  Probing", "warning")
        self.system_badge = ConnectionIndicator("System  Healthy", "success")
        for badge in (self.mqtt_badge, self.gps_badge, self.hardware_badge, self.system_badge): layout.addWidget(badge)
        fullscreen = QPushButton(); fullscreen.setIcon(icon("fullscreen")); fullscreen.setIconSize(QSize(20, 20)); fullscreen.setFixedSize(40, 40)

        fullscreen.setToolTip("Toggle full screen (F11)"); fullscreen.setAccessibleName("Toggle full screen"); fullscreen.clicked.connect(self.toggle_fullscreen); layout.addWidget(fullscreen)

        return bar



    def _live_page(self) -> QWidget:

        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(20, 16, 20, 16); layout.setSpacing(12)

        warning = QFrame(); warning.setObjectName("WarningBanner")

        warning_layout = QHBoxLayout(warning); warning_layout.setContentsMargins(12, 7, 12, 7)

        warning_title = QLabel("Simulation environment")
        self.mode_title = warning_title

        warning_title.setStyleSheet(f"color:{Color.AMBER}; font-weight:600;")

        warning_text = QLabel("Timings are for demonstration only. No physical road signals are controlled."); warning_text.setObjectName("Supporting")
        self.mode_description = warning_text
        warning_text.setWordWrap(True)

        warning_layout.addWidget(warning_title); warning_layout.addWidget(warning_text); warning_layout.addStretch(); layout.addWidget(warning)

        splitter = QSplitter(Qt.Orientation.Horizontal); splitter.setChildrenCollapsible(False)

        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.setContentsMargins(0, 0, 4, 0); left_layout.setSpacing(12)

        canvas = SectionCard()

        canvas_header = QHBoxLayout(); heading = QLabel("Live junction map"); heading.setObjectName("CardTitle")

        map_status = StatusBadge("Vector simulation", "info", "GPS coordinates are projected onto a software-only junction view")

        canvas_header.addWidget(heading); canvas_header.addStretch(); canvas_header.addWidget(map_status)

        canvas.body.addLayout(canvas_header); canvas.body.addWidget(self.view, 1); left_layout.addWidget(canvas, 1); left_layout.addWidget(self._simulation_controls())

        self.view.setMinimumHeight(240)
        self.view.setMaximumHeight(320)
        left_scroll = QScrollArea(); left_scroll.setObjectName("PageScroll")
        left_scroll.setWidgetResizable(True); left_scroll.setWidget(left)
        splitter.addWidget(left_scroll)

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

        top = QGridLayout(); top.setSpacing(Space.SM)

        self.start_button = PrimaryButton("Start normal cycle"); self.start_button.clicked.connect(self.resume_simulation)

        pause = SecondaryButton("Pause cycle"); pause.clicked.connect(self.pause_simulation)

        reset = SecondaryButton("Controlled reset"); reset.clicked.connect(self.reset_simulator)

        live = SecondaryButton("Live mobile GPS"); live.clicked.connect(self.enable_live_mode)

        built_in = SecondaryButton("Built-in simulation"); built_in.clicked.connect(self.enable_simulation_mode)
        stop = SecondaryButton("Stop safely"); stop.clicked.connect(self.stop_simulation)

        compact_labels = ("Start / Resume", "Pause", "Safe reset", "Live GPS", "Simulation", "Stop safely")

        tooltips = (

            "Start the normal traffic-signal state machine",

            "Pause the software signal cycle safely",

            "Reset to the all-red safe initialization state",

            "Receive live mobile GPS packets over MQTT",

            "Use internally generated, clearly marked simulated ambulances",
            "Finish passage and clearance, then stop in all-red",

        )

        for index, (button, label, tooltip) in enumerate(zip((self.start_button, pause, reset, live, built_in, stop), compact_labels, tooltips)):

            button.setText(label); button.setToolTip(tooltip); top.addWidget(button, index // 3, index % 3)

        card.body.addLayout(top)

        self.last_simulation_side = Approach.NORTH

        simulate = PrimaryButton("Add ambulance"); simulate.clicked.connect(self.open_simulation_dialog)

        second = SecondaryButton("Add second"); second.clicked.connect(self.add_second_ambulance)

        gps_loss = DangerButton("GPS loss"); gps_loss.clicked.connect(self.simulate_gps_loss)

        actions = QHBoxLayout(); actions.setSpacing(Space.SM)

        actions.addWidget(simulate, 1); actions.addWidget(second, 1); actions.addWidget(gps_loss, 1)

        card.body.addLayout(actions)

        physics = QGridLayout()

        add_car = SecondaryButton("Add vehicle")

        add_car.clicked.connect(self.add_ordinary_vehicle)

        step = SecondaryButton("Step tick")

        step.clicked.connect(self.step_simulation)

        speed_control = QComboBox(); speed_control.addItems(["0.5×", "1×", "2×", "5×"]); speed_control.setCurrentIndex(1)

        speed_control.currentIndexChanged.connect(lambda i: setattr(self, "simulation_speed", [0.5, 1, 2, 5][i]))

        for index, widget in enumerate((add_car, step, speed_control)): physics.addWidget(widget, 0, index)

        hardware = SecondaryButton("Monitor Raspberry Pi")
        hardware.clicked.connect(self.enable_hardware_monitor)
        physics.addWidget(hardware, 1, 0, 1, 3)
        hil = SecondaryButton("Hardware-in-the-loop · simulated GPS / Pi lamps")
        hil.clicked.connect(self.enable_hil_mode)
        physics.addWidget(hil, 2, 0, 1, 3)
        fault = QComboBox()
        fault.addItems(["Choose simulation fault", "GPS noise (8 m)", "Stop ambulance", "U-turn before junction", "Controller fault", "Restore simulated GPS / motion", "MQTT loss", "Restore MQTT", "Reject next priority request"])
        fault.activated.connect(lambda index:self.apply_simulation_fault(index))
        physics.addWidget(fault, 3, 0, 1, 3)
        card.body.addLayout(physics)

        self.traffic_metrics = QLabel(); self.traffic_metrics.setWordWrap(True)

        card.body.addWidget(self.traffic_metrics)

        return card



    def open_simulation_dialog(self) -> None:

        dialog = QDialog(self); dialog.setWindowTitle("Add simulated ambulance"); dialog.setMinimumWidth(430)

        root = QVBoxLayout(dialog); root.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL); root.setSpacing(Space.LG)

        heading = QLabel("Simulated ambulance setup"); heading.setObjectName("SectionTitle"); root.addWidget(heading)

        detail = QLabel("Generated telemetry is visibly marked SIMULATED and only operates the software model.")

        detail.setObjectName("Supporting"); detail.setWordWrap(True); root.addWidget(detail)

        form = QFormLayout(); form.setSpacing(Space.MD)

        side = QComboBox(); side.addItems([value.value.title() for value in Approach]); side.setCurrentText(self.last_simulation_side.value.title())
        destination = QComboBox()
        def refresh_destination():
            path=self.config.raw['geometry']['paths'][side.currentText().upper()]
            east,north=path[-1]
            exit_side=("EAST" if east>0 else "WEST") if abs(east)>abs(north) else ("NORTH" if north>0 else "SOUTH")
            destination.clear(); destination.addItem(exit_side.title())
        side.currentTextChanged.connect(refresh_destination); refresh_destination()
        destination.setToolTip("Only the registered movement for this inbound road can request priority. Configure its path and exit line in the junction registry.")

        priority = QComboBox(); priority.addItems(["Critical", "Serious", "Stable"])

        speed = QDoubleSpinBox(); speed.setRange(0.5, 35); speed.setValue(float(self.config.simulation["ambulance_speed_mps"])); speed.setSuffix(" m/s")

        accuracy = QDoubleSpinBox(); accuracy.setRange(1, 80); accuracy.setValue(float(self.config.simulation["gps_accuracy_metres"])); accuracy.setSuffix(" m")

        delay = QDoubleSpinBox(); delay.setRange(0.5, 5); delay.setSingleStep(0.5); delay.setValue(float(self.config.simulation["packet_delay_seconds"])); delay.setSuffix(" s")
        latency = QDoubleSpinBox(); latency.setRange(0,15); latency.setSuffix(" s")
        noise = QDoubleSpinBox(); noise.setRange(0,50); noise.setSuffix(" m")

        for label, field in (("Starting approach", side), ("Registered destination exit",destination), ("Medical priority", priority), ("Travel speed", speed), ("GPS accuracy", accuracy), ("Packet interval", delay), ("Network delay",latency), ("GPS noise standard deviation",noise)):

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
        self.simulations[-1].network_delay_seconds=latency.value()
        self.simulations[-1].noise_metres=noise.value()

    def add_ordinary_vehicle(self):
        dialog=QDialog(self); dialog.setWindowTitle("Add ordinary vehicle")
        layout=QFormLayout(dialog)
        inbound=QComboBox(); inbound.addItems([side.value for side in Approach])
        outbound=QComboBox(); outbound.addItems([side.value for side in Approach]); outbound.setCurrentText("SOUTH")
        layout.addRow("Inbound approach",inbound); layout.addRow("Outbound exit",outbound)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addRow(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        if inbound.currentText()==outbound.currentText():
            self.toast.show_message("Choose a different exit; ordinary U-turns are unsupported."); return
        if self.traffic.spawn(Approach(inbound.currentText()),Approach(outbound.currentText())) is None:
            self.toast.show_message("Spawn lane occupied; wait for the existing vehicle to move.")



    def _connect_page_actions(self) -> None:

        self.queue_page.cancel_requested.connect(lambda trip: self.cancel_trip(trip, "Cancelled by operator"))

        self.queue_page.hold_requested.connect(self.hold_request)

        self.queue_page.restore_requested.connect(self.restore_request)

        self.settings_page.settings_applied.connect(self.apply_settings)



    def show_page(self, index: int) -> None:

        self.page_stack.setCurrentIndex(index); self.page_title.setText(self.PAGE_TITLES[index]); self.nav_buttons[index].setChecked(True)

        if index == 2: self.history_page.refresh()
        if index == 6: self.logs_page.refresh()



    def toggle_fullscreen(self) -> None:

        if self.isFullScreen(): self.showNormal(); self.showMaximized()

        else: self.showFullScreen()



    def start_simulation(self, side: Approach | None = None, ambulance_id: str | None = None,

                         priority: PatientPriority = PatientPriority.RED, speed_mps: float | None = None,

                         accuracy_metres: float | None = None, packet_delay_seconds: float | None = None) -> None:

        if self.mqtt is not None or (self.hardware_monitor is not None and self.hil_adapter is None): self.enable_simulation_mode()
        selected_side = side or self.last_simulation_side; self.last_simulation_side = selected_side

        simulator = create_simulated_ambulance(

            self.config, selected_side, ambulance_id=ambulance_id, priority=priority,

            speed_mps=speed_mps if speed_mps is not None else float(self.config.simulation["ambulance_speed_mps"]),

            accuracy_metres=accuracy_metres if accuracy_metres is not None else float(self.config.simulation["gps_accuracy_metres"]),

            packet_delay_seconds=packet_delay_seconds if packet_delay_seconds is not None else float(self.config.simulation["packet_delay_seconds"]),

        )

        same_lane = [s.signed_distance_metres for s in self.simulations if s.starting_side==selected_side and not s.finished]
        if same_lane: simulator.signed_distance_metres=max(simulator.signed_distance_metres,max(same_lane)+12)
        simulator.advance_after_packet = False
        self.simulations.append(simulator); self.simulation_elapsed[simulator.trip_id] = simulator.packet_delay_seconds

        self._on_event("SIMULATION_STARTED", f"{simulator.ambulance_id} from {selected_side.value}; demo data marked simulated")



    def add_second_ambulance(self) -> None:

        current = self.last_simulation_side

        opposite = {Approach.NORTH: Approach.EAST, Approach.EAST: Approach.SOUTH, Approach.SOUTH: Approach.WEST, Approach.WEST: Approach.NORTH}[current]

        self.start_simulation(opposite, "SIM-SECOND")



    def process_packet(self, packet: TelemetryPacket) -> None:

        if self.hil_adapter is not None:
            try:
                result = self.hil_adapter.process(packet)
                self.latest_assessment = result
                if result.valid: self.scene.update_ambulance(result)
                self.gps_badge.set_connection("Simulated GPS", "Live" if result.valid else "Inaccurate")
                self.emergency_card.update_assessment(result,None)
            except ValueError as exc:
                self._on_event("HIL_MESSAGE_REJECTED",str(exc))
            return
        simulated = packet.trip_id in self.simulation_elapsed
        result = self.coordinator.process_packet(packet, self.simulation_clock if simulated else None); self.latest_assessment = result
        if simulated and result.eligible and self.reject_next_simulated_request:
            self.reject_next_simulated_request=False
            self.coordinator.cancel(packet.trip_id,"Simulated controller rejection")
            self.coordinator.outcomes[packet.trip_id]="REQUEST_REJECTED"
            self.coordinator._event("REQUEST_REJECTED","Simulated controller rejection",packet.trip_id)

        self.last_packet_at = datetime.now(timezone.utc); self.packet_times.append(self.last_packet_at); self.packet_times = self.packet_times[-20:]

        if result.valid:
            self.scene.update_ambulance(result); self.gps_badge.set_connection("GPS", "Live")
            approach_side = result.approach.value if result.approach else (packet.approach_side or "")
            if approach_side:
                compass = packet.compass_direction
                if not compass:
                    h_val = packet.travel_heading if packet.travel_heading is not None else packet.heading_degrees
                    compass_names = ["North", "North-East", "East", "South-East", "South", "South-West", "West", "North-West"]
                    compass = compass_names[int(((h_val + 22.5) % 360) // 45)]
                self.voice_announcer.announce_approach(packet.trip_id, approach_side, compass)
                self.statusBar().showMessage(f"Ambulance {packet.ambulance_id} arriving from {approach_side.title()} Approach (Heading {compass})")
        else:
            self.gps_badge.set_connection("GPS", "Inaccurate")



    def enable_live_mode(self) -> None:

        if self.hardware_monitor is not None: self.enable_simulation_mode()
        if self.mqtt is not None: return

        self.mqtt = MQTTClient(self.config, self.bridge.packet.emit, self.bridge.cancel.emit, self.bridge.state.emit,

                               self.bridge.error.emit, self.bridge.ambulance_status.emit)

        self.mqtt.start(); self._on_event("MODE_CHANGED", "Live phone telemetry / SIMULATION controller; hardware acknowledgements are not generated")



    def enable_simulation_mode(self) -> None:

        self.pending_packets.clear()
        if self.hil_adapter is not None:
            for trip in self.hil_adapter.sent:
                try: self.hil_adapter.cancel(trip)
                except ValueError: pass  # Pi's bounded timeout remains authoritative.
            self.hil_adapter = None
        if self.hardware_monitor is not None:
            self.hardware_monitor.stop(); self.hardware_monitor = None
            self.hardware_heartbeat = None
            self.coordinator.reset()
            self.scene.update_signals(self.coordinator.controller.signals)
        self.statusBar().showMessage("SIMULATION · Local controller; no physical outputs")
        self.mode_title.setText("Simulation environment")
        self.mode_footer.setText("SOFTWARE SIMULATION")
        self.mode_description.setText("Software controller and simulated lamps. Laboratory prototype only.")
        if self.mqtt:

            self.mqtt.stop(); self.mqtt = None

        self._mqtt_state("DISCONNECTED (SIMULATION)"); self._on_event("MODE_CHANGED", "Built-in simulation mode enabled")



    def enable_hardware_monitor(self):
        self.enable_simulation_mode()
        self.simulations.clear(); self.scene.clear_ambulances(); self.coordinator.reset()
        self.hardware_heartbeat = None
        self.hardware_acks.clear()
        self.hardware_passage_events.clear()
        self.hardware_monitor = HardwareMonitor(self.config,self.bridge.hardware.emit,self.bridge.state.emit)
        self.hardware_monitor.start()
        self.signal_card.badge.set_status("Awaiting hardware", "warning")
        self.system_badge.set_status("Pi · Awaiting heartbeat","warning")
        for row in (self.signal_card.phase,self.signal_card.machine,self.signal_card.remaining,self.signal_card.selected,self.signal_card.direction): row.value.setText("Unknown")
        self.statusBar().showMessage("LIVE HARDWARE MONITOR · Awaiting actual Raspberry Pi heartbeat")
        self._on_event("MODE_CHANGED","Live hardware monitor; local controller disabled")
        self.mode_title.setText("Live hardware monitor")
        self.mode_footer.setText("HARDWARE MONITOR")
        self.mode_footer.setToolTip("Actual Raspberry Pi laboratory LED model")
        self.mode_description.setText("Actual Raspberry Pi lamp states; laboratory LED model only.")

    def enable_hil_mode(self):
        from ..simulator.simulation_adapter import SimulationAdapter
        self.enable_hardware_monitor()
        self.hil_adapter = SimulationAdapter(self.config,self.hardware_monitor.secrets,self.hardware_monitor.publish_simulation)
        self.simulation_speed = 1.0
        self.mode_title.setText("Hardware-in-the-loop")
        self.mode_footer.setText("HARDWARE-IN-THE-LOOP")
        self.mode_description.setText("SIMULATED ambulance GPS · ACTUAL Pi lamps · real-time laboratory test")
        self.statusBar().showMessage("HIL · Waiting for actual Pi heartbeat; provision SIM identities before adding ambulances")

    def receive_hardware(self,data):
        if self.hardware_monitor is None: return
        if data.get("controllerId") != self.config.junction["controller_id"]: return
        if data.get("messageType")=="AUTHENTICATED_TELEMETRY":
            packet=TelemetryPacket.from_dict(data["packet"])
            assessment=self.coordinator.gps.assess(packet)
            self.latest_assessment=assessment
            if assessment.valid:
                self.last_packet_at=packet.timestamp
                self.scene.update_ambulance(assessment)
                self.emergency_card.update_assessment(assessment,None)
            self.gps_badge.set_connection("Simulated GPS" if data.get("sourceMode")=="SIMULATION" else "Phone GPS","Live" if assessment.valid else "Inaccurate")
            return
        if data.get("online") is True and data.get("timestamp"):
            from ..core.models import parse_timestamp
            try:
                stamp=parse_timestamp(data["timestamp"])
                if not 0 <= (datetime.now(timezone.utc)-stamp).total_seconds() <= 5: return
                lamps={Approach(k):SignalColour(v) for k,v in data["lampState"].items()}
                if set(lamps)!=set(Approach): return
            except (ValueError,KeyError,TypeError): return
            self.hardware_heartbeat=time.monotonic(); self.hardware_lamps=lamps
            self.system_badge.set_status("Pi · Fail-safe" if data.get("controllerState")=="FAIL_SAFE" else "Pi · Heartbeat live",
                "critical" if data.get("controllerState")=="FAIL_SAFE" else "success")
            self.scene.update_signals(lamps)
            self.signal_card.badge.set_status("Hardware state", "info")
            self.signal_card.machine.value.setText(data.get("controllerState","UNKNOWN"))
            self.signal_card.phase.value.setText(" / ".join(f"{s.value}:{c.value}" for s,c in lamps.items()))
            self.controller_details.setText("HARDWARE · "+data.get("controllerState","UNKNOWN"))
            self.statusBar().showMessage("LIVE HARDWARE MONITOR · Actual Raspberry Pi lamp state")
        if data.get("messageType")=="PRIORITY_ACK":
            self.hardware_acks[data["requestId"]]=data
            self.queue_panel.update_hardware(list(self.hardware_acks.values()))
            result="Priority granted" if data.get("verifiedGrant") else "Controller acknowledgement; grant unconfirmed"
            self.signal_card.selected.value.setText(data.get("ambulanceId","Unknown"))
            self.signal_card.direction.value.setText(data.get("grantedApproach", "Unconfirmed"))
            self.signal_card.badge.set_status(result,"success" if data.get("verifiedGrant") else "warning")
            self._on_event("HARDWARE_ACK",result+" · "+data.get("requestId",""))
            self.structured_log.record(sourceComponent="raspberry_pi",eventType="HARDWARE_ACK",tripId=data["tripId"],requestId=data["requestId"],
                ambulanceId=data["ambulanceId"],junctionId=data["junctionId"],approachSide=data.get("grantedApproach"),
                controllerState=data.get("controllerState"),signalState=data.get("lampState"),result=result,
                failureReason=data.get("rejectionReason") if not data.get("accepted") else None)
            passage_event={"STOP_LINE_CROSSED":"JUNCTION_ENTERED","INSIDE_JUNCTION":"JUNCTION_ENTERED",
                           "JUNCTION_CLEARED":"JUNCTION_CLEARED","NORMAL_RESTORING":"JUNCTION_CLEARED","COMPLETED":"NORMAL_RESTORED"}.get(data.get("junctionState"))
            key=(data["requestId"],passage_event)
            if data.get("accepted") and passage_event and key not in self.hardware_passage_events:
                self.hardware_passage_events.add(key)
                self.structured_log.record(timestamp=data['acknowledgementTimestamp'],sourceComponent="raspberry_pi",eventType=passage_event,
                    tripId=data['tripId'],requestId=data['requestId'],ambulanceId=data['ambulanceId'],junctionId=data['junctionId'],
                    controllerState=data['controllerState'],signalState=data['lampState'],result="Authenticated controller passage confirmation")

    def simulate_gps_loss(self) -> None:

        active = next((item for item in reversed(self.simulations) if not item.finished), None)

        if active:

            active.gps_enabled = False; self._on_event("GPS_CONNECTION_LOST", f"Simulated GPS loss for {active.trip_id}")

        else:

            self._on_event("GPS_LOSS_IGNORED", "No active simulated ambulance")

            self.toast.show_message("No active simulated ambulance is available for GPS-loss testing.")

    def apply_simulation_fault(self,index):
        if index == 0: return
        if index==8:
            if self.hil_adapter is not None: self.hil_adapter.reject_next=True
            elif self.hardware_monitor is None: self.reject_next_simulated_request=True
            else:
                self.toast.show_message("Use Simulation or HIL to inject a request rejection."); return
            self._on_event("REJECTION_ARMED","Next simulated priority request will exercise controller rejection")
            return
        if index in {6,7}:
            self.simulated_network_available=index==7
            self.pending_packets.clear()
            if self.hardware_monitor is not None:
                if index==6:
                    self.hardware_monitor.client.disconnect(); self.hardware_heartbeat=None
                else: self.hardware_monitor.client.reconnect()
            else:
                self.mqtt_badge.set_connection("Simulated MQTT", "Lost" if index==6 else "Available")
            self._on_event("SIMULATED_MQTT_LOSS" if index==6 else "SIMULATED_MQTT_RESTORED","Scenario network state changed")
            return
        if self.hardware_monitor is not None:
            self.toast.show_message("Use isolated software Simulation mode for injected controller and motion faults."); return
        if index == 4:
            self.coordinator.controller._enter_fail_safe("Injected simulation controller fault")
            self._refresh_panels(); return
        ambulance = next((s for s in reversed(self.simulations) if s.active and not s.finished),None)
        if ambulance is None:
            self.toast.show_message("Add a simulated ambulance first."); return
        if index == 1: ambulance.noise_metres=8
        elif index == 2: ambulance.stopped=True
        elif index == 3:
            if ambulance.signed_distance_metres <= 25:
                self.toast.show_message("This U-turn scenario must start before the stop line."); return
            ambulance.reversing=True
        elif index == 5:
            ambulance.gps_enabled=True; ambulance.stopped=False; ambulance.noise_metres=0
        self._on_event("SIMULATION_FAULT",f"Scenario control {index} applied to {ambulance.trip_id}")



    def cancel_selected(self) -> None:

        trip_id = self.queue_panel.selected_trip_id() or self.coordinator.controller.target_trip_id

        if trip_id and ConfirmationDialog.confirm(self, "Cancel request", "Cancel the selected emergency request?", "Cancel request", True): self.cancel_trip(trip_id)



    def cancel_trip(self, trip_id: str, reason: str = "Emergency trip cancelled") -> None:

        if self.hil_adapter is not None:
            try: self.hil_adapter.cancel(trip_id)
            except ValueError as exc: self._on_event("HIL_CANCEL_FAILED",str(exc))
        request = self.coordinator.priority.get(trip_id)

        self.coordinator.cancel(trip_id, reason); self.scene.hide_ambulance(trip_id)

        if self.mqtt and request:

            self.mqtt.publish_request(

                request.ambulance_id, request.trip_id, "CANCELLED",

                str(request.metadata.get("requestId", "")), request.approach.value,

                self.coordinator.controller.state.value, reason,

            )

        for simulation in self.simulations:

            if simulation.trip_id == trip_id: simulation.active = False



    def hold_request(self, trip_id: str) -> None:

        if self.coordinator.priority.hold(trip_id): self._on_event("REQUEST_HELD", f"{trip_id} temporarily held by operator")

        else: self.toast.show_message("The active controller request cannot be held.")



    def restore_request(self, trip_id: str) -> None:

        if self.coordinator.priority.restore(trip_id): self._on_event("REQUEST_RESTORED", f"{trip_id} restored to automatic priority ordering")



    def reset_simulator(self) -> None:

        if self.hardware_monitor is not None:
            self.toast.show_message("Reset is available in software Simulation mode. Recover physical faults at the Pi controller."); return
        if self.coordinator.controller.controlled_reset_required and not ConfirmationDialog.confirm(

            self, "Controlled reset", "Reset the fail-safe latch and initialize every approach to red?", "Reset safely", True): return

        self.traffic = TrafficEngine(); self.scene.clear_traffic()
        self.pending_packets.clear(); self.simulated_network_available=True
        self.simulation_clock = datetime.now(timezone.utc)
        self.traffic_spawn_elapsed = 0.0

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
        self.controller_view.setScene(self.scene)

        if old_broker != (self.config.mqtt["broker"], int(self.config.mqtt["port"])) and not os.getenv("LIFELANE_MQTT_HOST"):

            if self.mqtt: self.mqtt.stop(); self.mqtt = None

            self.enable_live_mode()

        self._on_event("CONFIG_UPDATED", "Validated junction settings applied")

        self.toast.show_message("Settings validated and applied.")



    def _tick(self) -> None:

        self.check_hardware_freshness()
        wall = time.monotonic()

        step = min(0.2, max(0, wall-self.last_tick)) * (1.0 if self.hardware_monitor is not None else self.simulation_speed)

        self.last_tick = wall

        if not self.traffic.running:

            return

        self._advance_simulation(step)



    def resume_simulation(self):

        self.stop_at_all_red = False
        self.traffic.running = True

        self.coordinator.controller.start()

        self.last_tick = time.monotonic()



    def pause_simulation(self):

        self.traffic.running = False

        self.coordinator.controller.pause()

    def stop_simulation(self):
        if self.hardware_monitor is not None:
            self.pause_simulation()
            self.statusBar().showMessage("Hardware vehicle display stopped; Pi controller remains authoritative")
            return
        self.stop_at_all_red=True
        self.traffic.running=True; self.coordinator.controller.start()
        for simulation in self.simulations:
            if not self.coordinator.passage.entered_zone(simulation.trip_id):
                self.cancel_trip(simulation.trip_id,"Simulation stopped before junction entry")
        self._on_event("SIMULATION_STOPPING","Waiting for safe all-red; occupied junctions continue to clearance")



    def step_simulation(self):

        if self.traffic.running:

            return

        self.resume_simulation()

        self._advance_simulation(0.05)

        self.pause_simulation()



    def _advance_simulation(self, step):

        if self.hardware_monitor is not None:
            if self.last_packet_at is not None and (datetime.now(timezone.utc)-self.last_packet_at).total_seconds()>self.config.detection['maximum_packet_age_seconds']:
                self.gps_badge.set_connection("GPS","Stale")
            if self.hardware_heartbeat is None or time.monotonic()-self.hardware_heartbeat > 5:
                self.signal_card.badge.set_status("Heartbeat lost / awaiting hardware", "warning")
                self.system_badge.set_status("Pi · Heartbeat unavailable","critical")
                self.statusBar().showMessage("HARDWARE · Lamp state last known; vehicle simulation paused")
                return
            self.traffic_spawn_elapsed += step
            if self.traffic_spawn_elapsed >= 3:
                self.traffic_spawn_elapsed %= 3
                for side in Approach: self.traffic.spawn(side)
            self.traffic.obstacles = [Vehicle(s.trip_id,s.starting_side,200-s.signed_distance_metres,s.velocity_mps,length=5,destination=s.exit_side)
                                      for s in self.simulations if s.active and not s.finished]
            self.traffic.tick(step, self.hardware_lamps)
            if self.hil_adapter is not None:
                for simulation in list(self.simulations):
                    if not simulation.active: continue
                    progress = 200-simulation.signed_distance_metres
                    leaders = [v.progress-v.length-self.traffic.GAP-progress for v in self.traffic.vehicles
                               if v.approach==simulation.starting_side and v.progress>progress]
                    leaders += [200-s.signed_distance_metres-5-self.traffic.GAP-progress for s in self.simulations
                                if s is not simulation and s.active and s.starting_side==simulation.starting_side and 200-s.signed_distance_metres>progress]
                    if simulation.signed_distance_metres>20.5 and any(v.approach!=simulation.starting_side and self.traffic.STOP<v.progress<v.exit_progress+v.length+self.traffic.GAP for v in self.traffic.vehicles):
                        leaders.append(simulation.signed_distance_metres-20.5)
                    simulation.advance(step,self.hardware_lamps[simulation.starting_side],min(leaders,default=float("inf")))
                    self.simulation_elapsed[simulation.trip_id] = self.simulation_elapsed.get(simulation.trip_id,0)+step
                    if self.simulation_elapsed[simulation.trip_id] >= simulation.packet_delay_seconds:
                        self.simulation_elapsed[simulation.trip_id] = 0
                        packet = simulation.next_packet(datetime.now(timezone.utc))
                        if packet: self.queue_simulated_packet(packet,simulation,datetime.now(timezone.utc))
                    if simulation.finished: self.simulations.remove(simulation)
                self.deliver_simulated_packets(datetime.now(timezone.utc))
            self.scene.update_traffic(self.traffic)
            self.scene.update_signals(self.hardware_lamps)
            self.metrics_page.refresh(self.traffic,self.structured_log,list(self.hardware_acks.values()))
            return

        self.simulation_clock += timedelta(seconds=step)
        now = datetime.now(timezone.utc) if self.mqtt is not None else self.simulation_clock

        self.traffic_spawn_elapsed += step

        if self.traffic_spawn_elapsed >= 3 and not self.stop_at_all_red:

            self.traffic_spawn_elapsed %= 3

            for side in Approach: self.traffic.spawn(side)

        self.traffic.obstacles = [Vehicle(s.trip_id,s.starting_side,200-s.signed_distance_metres,s.velocity_mps,length=5,destination=s.exit_side)
                                  for s in self.simulations if s.active and not s.finished]
        self.traffic.tick(step, self.coordinator.controller.signals)
        for simulation in self.simulations:
            if not simulation.active: continue
            progress = 200-simulation.signed_distance_metres
            ahead = [v.progress-v.length-self.traffic.GAP-progress for v in self.traffic.vehicles
                     if v.approach==simulation.starting_side and v.progress>progress]
            ahead += [200-s.signed_distance_metres-5-self.traffic.GAP-progress for s in self.simulations
                      if s is not simulation and s.starting_side==simulation.starting_side and 200-s.signed_distance_metres>progress]
            if simulation.signed_distance_metres>20.5 and any(v.approach!=simulation.starting_side and self.traffic.STOP<v.progress<v.exit_progress+v.length+self.traffic.GAP for v in self.traffic.vehicles):
                ahead.append(simulation.signed_distance_metres-20.5)
            simulation.advance(step,self.coordinator.controller.signals[simulation.starting_side],min(ahead,default=float("inf")))

        self.scene.update_traffic(self.traffic)

        metrics = self.traffic.metrics()

        self.traffic_metrics.setText(

            f"Generated {metrics['generated']} · Cleared {metrics['cleared']} · "

            f"Mean wait {metrics['averageWaitingSeconds']:.1f}s · Max wait {metrics['maximumWaitingSeconds']:.1f}s\n"

            + " · ".join(f"{side}: {n}" for side, n in metrics['queues'].items()))

        for simulation in list(self.simulations):

            self.simulation_elapsed[simulation.trip_id] = self.simulation_elapsed.get(simulation.trip_id, 0) + step

            if self.simulation_elapsed[simulation.trip_id] >= simulation.packet_delay_seconds:

                self.simulation_elapsed[simulation.trip_id] = 0.0; packet = simulation.next_packet(now)

                if packet: self.queue_simulated_packet(packet,simulation,now)

            if simulation.finished: self.simulations.remove(simulation)

        self.deliver_simulated_packets(now)
        self.coordinator.tick(step, now); self.status_elapsed += step; self.health_elapsed += step

        if self.mqtt and self.status_elapsed >= 1.0:

            self.status_elapsed = 0.0; selected = self.coordinator.priority.get(self.coordinator.controller.target_trip_id or "")

            self.mqtt.publish_status({"online": True, "preemptionState": self.coordinator.controller.state.value,

                "signalState": ",".join(f"{side.value}:{colour.value}" for side, colour in self.coordinator.controller.signals.items()),

                "selectedAmbulance": selected.ambulance_id if selected else "", "requestStatus": selected.status.value if selected else "NONE"})
        ctrl = self.coordinator.controller
        self.scene.update_signals(ctrl.signals)
        self.scene.update_traffic(step, ctrl.signals, ctrl.state, ctrl.target_approach)
        if hasattr(self, "hardware_bridge") and self.hardware_bridge:
            self.hardware_bridge.send_signals(ctrl.signals, ctrl.state)
        self._refresh_panels()
        if self.stop_at_all_red and self.coordinator.controller.state is PreemptionState.NORMAL and all(c is SignalColour.RED for c in self.coordinator.controller.signals.values()):
            self.stop_at_all_red = False
            self.pause_simulation()
            self._on_event("SIMULATION_STOPPED", "Stopped with every approach red")
        if hasattr(self, "metrics_page") and hasattr(self, "traffic") and hasattr(self, "structured_log"):
            self.metrics_page.refresh(self.traffic, self.structured_log)
        if hasattr(self, "controller_details"):
            self.controller_details.setText(f"SIMULATION controller | {ctrl.state.value} | {ctrl.normal_phase.value} | {ctrl.elapsed:.1f}s | MQTT: {self.mqtt_state}")
        if self.health_elapsed >= 1.0:

            self.health_elapsed = 0.0

            self._refresh_health()

            self.queue_page.refresh_outcomes()



    def queue_simulated_packet(self,packet,simulation,now):
        if self.simulated_network_available:
            self.pending_packets.append((now+timedelta(seconds=simulation.network_delay_seconds),packet))

    def check_hardware_freshness(self):
        if self.hardware_monitor is None: return
        if self.hardware_heartbeat is None or time.monotonic()-self.hardware_heartbeat>5:
            self.system_badge.set_status("Pi · Heartbeat unavailable","critical")
            self.signal_card.badge.set_status("Last known state · unconfirmed","warning")
        if self.last_packet_at and (datetime.now(timezone.utc)-self.last_packet_at).total_seconds()>self.config.detection['maximum_packet_age_seconds']:
            self.gps_badge.set_connection("GPS","Stale")

    def deliver_simulated_packets(self,now):
        due=[item for item in self.pending_packets if item[0]<=now]
        self.pending_packets=[item for item in self.pending_packets if item[0]>now]
        for _,packet in sorted(due,key=lambda item:item[0]): self.process_packet(packet)

    def _remaining_time(self) -> float | None:

        controller = self.coordinator.controller; timing = self.config.timing

        if not controller.running: return None

        if controller.state is PreemptionState.NORMAL:

            duration = controller.normal_phase_duration
        elif controller.state in {PreemptionState.CLEAR_CURRENT_GREEN, PreemptionState.RECOVERY_YELLOW}: duration = timing["yellow_seconds"]

        elif controller.state in {PreemptionState.ALL_RED_CLEARANCE, PreemptionState.RECOVERY_ALL_RED}: duration = timing["all_red_seconds"]

        elif controller.state is PreemptionState.PREEMPTION_PENDING: duration = controller._pending_minimum_green

        elif controller.state in {PreemptionState.REQUEST_VALIDATION, PreemptionState.AMBULANCE_GREEN}: duration = 0.0

        elif controller.state is PreemptionState.PASSAGE_MONITORING: duration = timing["maximum_ambulance_green_seconds"]

        else: return None

        return max(0.0, float(duration) - controller.elapsed)



    def _refresh_panels(self) -> None:

        if self.hardware_monitor is not None: return
        fault=self.coordinator.controller.state is PreemptionState.FAIL_SAFE
        self.system_badge.set_status("Simulation · Fail-safe" if fault else "Simulation · Healthy","critical" if fault else "success")
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
        if hasattr(self, "hardware_bridge") and self.hardware_bridge and hasattr(self, "hardware_badge"):
            if self.hardware_bridge.is_connected and self.hardware_bridge.connected_port:
                if "Offline" in self.hardware_badge.text() or "Probing" in self.hardware_badge.text():
                    self.hardware_badge.set_connection("ESP32", f"Connected ({self.hardware_bridge.connected_port})")

    def _on_hardware_status_callback(self, connected: bool, port_or_msg: str) -> None:
        self.bridge.hardware_status.emit(connected, port_or_msg)

    def _handle_hardware_status(self, connected: bool, port_or_msg: str) -> None:
        if not hasattr(self, "hardware_badge"):
            return
        if connected:
            self.hardware_badge.set_connection("ESP32", f"Connected ({port_or_msg})")
            self._on_event("HARDWARE_CONNECTED", f"Physical traffic light connected on {port_or_msg}")
        else:
            self.hardware_badge.set_connection("ESP32", port_or_msg if "Offline" in port_or_msg else "Offline")



    def _mqtt_state(self, state: str) -> None:

        if self.mqtt is None and self.hardware_monitor is None and state in {"CONNECTED", "CONNECTING", "RECONNECTING", "DISCONNECTED"}:

            return  # Ignore callbacks queued before switching to simulation.

        self.mqtt_state = state; display = state.split(" ", 1)[0]; self.mqtt_badge.set_connection("MQTT", display); self._on_event("MQTT_STATE", state)



    def _on_ambulance_status(self, ambulance_id: str, online: bool) -> None:

        if not ambulance_id: return

        self.ambulance_states[ambulance_id] = online

        self._on_event("AMBULANCE_STATUS", f"{ambulance_id} is {'online' if online else 'offline'}")



    def _on_event(self, event_type: str, message: str) -> None:

        controller_events = self.coordinator.events.events if hasattr(self,"coordinator") else []
        if controller_events and controller_events[-1]["eventType"]==event_type and controller_events[-1]["result"]==message:
            self.structured_log.record(**controller_events[-1])
        else:
            self.structured_log.record(sourceComponent="windows_simulation",eventType=event_type,result=message,
                junctionId=self.config.junction["id"],tripId=self.coordinator.controller.target_trip_id if hasattr(self,"coordinator") else None)
        LOGGER.info("%s %s", event_type, message); self.event_panel.append_event(event_type, message)

        if event_type == "GPS_CONNECTION_LOST": self.gps_badge.set_connection("GPS", "Lost"); self.emergency_card.show_gps_loss(); self.toast.show_message(message, 6000)

        elif event_type in {"CRITICAL_FAIL_SAFE", "MQTT_ERROR", "CONFIG_ERROR"}: self.toast.show_message(message, 7000)

        elif event_type == "AMBULANCE_SELECTED": self.toast.show_message(message)

        if self.mqtt and event_type not in {"GPS_PACKET", "NORMAL_PHASE"}:

            self.mqtt.publish_event(event_type, message)

            if event_type in {"REQUEST_ACCEPTED", "AMBULANCE_SELECTED", "AMBULANCE_GREEN"}:

                request = self.coordinator.priority.get(self.coordinator.controller.target_trip_id or "")

                if request:

                    self.mqtt.publish_request(

                        request.ambulance_id, request.trip_id, request.status.value,

                        str(request.metadata.get("requestId", "")), request.approach.value,

                        self.coordinator.controller.state.value, message,

                    )



    def _update_clock(self) -> None:

        self.clock.setText(datetime.now().astimezone().strftime("%a, %d %b %Y\n%H:%M:%S"))



    def resizeEvent(self, event) -> None:  # noqa: N802

        super().resizeEvent(event)

        if hasattr(self, "toast") and self.toast.isVisible(): self.toast.move(max(16, self.width() - self.toast.width() - 24), 82)



    def closeEvent(self, event) -> None:  # noqa: N802

        self.timer.stop(); self.clock_timer.stop()
        if self.hardware_monitor: self.hardware_monitor.stop()

        if self.mqtt: self.mqtt.stop()
        if hasattr(self, "hardware_bridge") and self.hardware_bridge:
            self.hardware_bridge.stop()
        self.repository.connection.close(); super().closeEvent(event)

