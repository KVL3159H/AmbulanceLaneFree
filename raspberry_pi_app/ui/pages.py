"""Secondary desktop pages for queue operations, history, health and settings."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.config import JunctionConfig
from ..core.models import PriorityRequest, RequestStatus
from ..database.repository import Repository
from .components import (
    ConfirmationDialog,
    DangerButton,
    EmptyState,
    MetricCard,
    PrimaryButton,
    SecondaryButton,
    SectionCard,
    StatusBadge,
)
from .theme import Color, Space


def page_header(title: str, subtitle: str) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setSpacing(2)
    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    supporting = QLabel(subtitle)
    supporting.setObjectName("PageContext")
    supporting.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(supporting)
    return layout


class EmergencyQueuePage(QWidget):
    cancel_requested = Signal(str)
    hold_requested = Signal(str)
    restore_requested = Signal(str)

    def __init__(self, repository: Repository) -> None:
        super().__init__()
        self.repository = repository
        root = QVBoxLayout(self)
        root.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.XL)
        root.setSpacing(Space.LG)
        root.addLayout(page_header("Emergency Queue", "Manage validated ambulance requests without bypassing signal safety rules."))
        self.summary = QHBoxLayout()
        self.active_metric = MetricCard("Active ambulance", "None")
        self.waiting_metric = MetricCard("Waiting requests", "0")
        self.held_metric = MetricCard("Temporarily held", "0")
        for card in (self.active_metric, self.waiting_metric, self.held_metric): self.summary.addWidget(card)
        root.addLayout(self.summary)
        card = SectionCard("Request management", "Manual actions are unavailable for the actively controlled ambulance.")
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["Position", "Ambulance", "Trip", "Approach", "Priority", "Distance", "ETA", "Waiting", "Status", "Reason"])
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.empty = EmptyState("Queue is clear", "No active, waiting, held or recently rejected emergency requests.")
        card.body.addWidget(self.empty)
        card.body.addWidget(self.table)
        actions = QHBoxLayout()
        self.hold_button = SecondaryButton("Temporarily hold")
        self.restore_button = PrimaryButton("Restore request")
        self.cancel_button = DangerButton("Cancel invalid request")
        self.hold_button.clicked.connect(self._hold)
        self.restore_button.clicked.connect(self._restore)
        self.cancel_button.clicked.connect(self._cancel)
        actions.addWidget(self.hold_button); actions.addWidget(self.restore_button); actions.addStretch(); actions.addWidget(self.cancel_button)
        card.body.addLayout(actions)
        outcomes = SectionCard("Completed and rejected requests", "Terminal request outcomes remain visible with their recorded reason.")
        self.outcomes = QTableWidget(0, 8)
        self.outcomes.setHorizontalHeaderLabels(["Time", "Trip", "Ambulance", "Priority", "Approach", "Signal wait", "Outcome", "Reason"])
        self.outcomes.setAlternatingRowColors(True); self.outcomes.verticalHeader().setVisible(False)
        self.outcomes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.outcomes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.outcomes.horizontalHeader().setStretchLastSection(True)
        self.outcome_empty = EmptyState("No completed requests", "Completed, cancelled and rejected request attempts will appear here.")
        outcomes.body.addWidget(self.outcome_empty); outcomes.body.addWidget(self.outcomes)
        panels = QSplitter(Qt.Orientation.Vertical); panels.setChildrenCollapsible(False)
        panels.addWidget(card); panels.addWidget(outcomes); panels.setStretchFactor(0, 3); panels.setStretchFactor(1, 2)
        root.addWidget(panels, 1)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self._update_actions()
        self.refresh_outcomes()

    def update_requests(self, requests: list[PriorityRequest], active_trip: str | None) -> None:
        self.empty.setVisible(not requests); self.table.setVisible(bool(requests))
        self.table.setRowCount(len(requests))
        now = datetime.now(timezone.utc)
        held = sum(request.status is RequestStatus.HELD for request in requests)
        waiting = sum(request.status is not RequestStatus.HELD and request.trip_id != active_trip for request in requests)
        active = next((request.ambulance_id for request in requests if request.trip_id == active_trip), "None")
        self.active_metric.set_value(active); self.waiting_metric.set_value(str(waiting)); self.held_metric.set_value(str(held))
        colours = {"RED": Color.RED, "YELLOW": Color.AMBER, "GREEN": Color.GREEN}
        priority_names = {"RED": "Critical", "YELLOW": "Serious", "GREEN": "Stable"}
        for row, request in enumerate(requests):
            wait = max(0, int((now - request.first_requested_at).total_seconds()))
            status = "Active" if request.trip_id == active_trip else request.status.value.title()
            reason = "Signal controller owns this request" if request.trip_id == active_trip else (
                "Held by operator" if request.status is RequestStatus.HELD else "Validated GPS request"
            )
            values = [str(row + 1), request.ambulance_id, request.trip_id, request.approach.value.title(),
                      priority_names[request.priority.value], f"{request.distance_metres:.0f} m",
                      f"{request.eta_seconds:.1f} s" if request.eta_seconds is not None else "—", f"{wait} s", status, reason]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole, request.trip_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, request.status.value)
                item.setData(Qt.ItemDataRole.UserRole + 2, request.trip_id == active_trip)
                if column == 4: item.setForeground(QColor(colours[request.priority.value]))
                if request.trip_id == active_trip: item.setBackground(QColor("#DBEAFE"))
                self.table.setItem(row, column, item)
        self._update_actions()

    def _selected(self) -> tuple[str | None, str, bool]:
        row = self.table.currentRow(); item = self.table.item(row, 0) if row >= 0 else None
        if item is None: return None, "", False
        return str(item.data(Qt.ItemDataRole.UserRole)), str(item.data(Qt.ItemDataRole.UserRole + 1)), bool(item.data(Qt.ItemDataRole.UserRole + 2))

    def _update_actions(self) -> None:
        trip, status, active = self._selected()
        self.hold_button.setEnabled(bool(trip) and not active and status != RequestStatus.HELD.value)
        self.restore_button.setEnabled(bool(trip) and status == RequestStatus.HELD.value)
        self.cancel_button.setEnabled(bool(trip) and not active)
        self.hold_button.setToolTip("Active preemption requests cannot be held" if active else "Pause queue consideration for this request")
        self.cancel_button.setToolTip("The active request remains controlled by the safety state machine" if active else "Cancel a request after operator confirmation")

    def _hold(self) -> None:
        trip, _status, _active = self._selected()
        if trip and ConfirmationDialog.confirm(self, "Hold request", "Temporarily remove this request from automatic selection?", "Hold request"):
            self.hold_requested.emit(trip)

    def _restore(self) -> None:
        trip, _status, _active = self._selected()
        if trip and ConfirmationDialog.confirm(self, "Restore automatic mode", "Return this held request to automatic medical-priority ordering?", "Restore request"):
            self.restore_requested.emit(trip)

    def _cancel(self) -> None:
        trip, _status, _active = self._selected()
        if trip and ConfirmationDialog.confirm(self, "Cancel invalid request", "Cancel this request? The action is recorded and cannot be undone.", "Cancel request", True):
            self.cancel_requested.emit(trip)

    def refresh_outcomes(self) -> None:
        rows = self.repository.recent_request_outcomes()
        self.outcome_empty.setVisible(not rows); self.outcomes.setVisible(bool(rows)); self.outcomes.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            wait = "—"
            if row.get("selected_time") and row.get("green_time"):
                try:
                    wait = f"{max(0, (datetime.fromisoformat(str(row['green_time'])) - datetime.fromisoformat(str(row['selected_time']))).total_seconds()):.1f} s"
                except ValueError:
                    pass
            approach = TripHistoryPage._approach(row.get("selected_reason"))
            occurred = TripHistoryPage._stamp(row.get("occurred"))
            reason = str(row.get("reason") or "Completed by the signal state machine")
            values = [occurred, row.get("trip_id"), row.get("ambulance_id"), row.get("priority"), approach, wait,
                      str(row.get("outcome") or "—").replace("_", " ").title(), reason]
            for column, value in enumerate(values):
                self.outcomes.setItem(row_index, column, QTableWidgetItem(str(value or "—")))


class TripHistoryPage(QWidget):
    def __init__(self, repository: Repository) -> None:
        super().__init__()
        self.repository = repository
        root = QVBoxLayout(self); root.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.XL); root.setSpacing(Space.LG)
        root.addLayout(page_header("Trip History", "Operational trip records stored in the local SQLite database."))
        tools = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search trip, ambulance, condition or destination"); self.search.setClearButtonEnabled(True)
        self.status = QComboBox(); self.status.addItems(["All results", "ACTIVE", "DELIVERED_THROUGH_JUNCTION", "PREEMPTION_TIMEOUT", "CANCELLED"])
        self.priority = QComboBox(); self.priority.addItems(["All priorities", "RED", "YELLOW", "GREEN"])
        refresh = SecondaryButton("Refresh"); refresh.clicked.connect(self.refresh)
        self.search.textChanged.connect(self.refresh); self.status.currentTextChanged.connect(self.refresh); self.priority.currentTextChanged.connect(self.refresh)
        for widget in (self.search, self.status, self.priority, refresh): tools.addWidget(widget)
        root.addLayout(tools)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["Trip ID", "Ambulance", "Priority", "Condition", "Started", "Completed", "Approach", "Signal wait", "Destination", "Result"])
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setStretchLastSection(True)
        self.empty = EmptyState("No trip history", "Completed and active GPS trips will be stored here.")
        root.addWidget(self.empty); root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self, *_args) -> None:
        status = "" if self.status.currentText() == "All results" else self.status.currentText()
        priority = "" if self.priority.currentText() == "All priorities" else self.priority.currentText()
        rows = self.repository.list_trips(self.search.text().strip(), status, priority)
        self.empty.setVisible(not rows); self.table.setVisible(bool(rows)); self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            wait = "—"
            if row["selected_time"] and row["green_time"]:
                try:
                    start = datetime.fromisoformat(row["selected_time"]); end = datetime.fromisoformat(row["green_time"])
                    wait = f"{max(0, (end - start).total_seconds()):.1f} s"
                except ValueError: pass
            values = [row["trip_id"], row["ambulance_id"], row["priority"], str(row["condition"]).replace("_", " ").title(),
                      self._stamp(row["start_time"]), self._stamp(row["end_time"]), self._approach(row["selected_reason"]), wait,
                      row["destination"], str(row["status"]).replace("_", " ").title()]
            for column, value in enumerate(values): self.table.setItem(row_index, column, QTableWidgetItem(str(value or "—")))

    @staticmethod
    def _stamp(value) -> str:
        if not value: return "—"
        try: return datetime.fromisoformat(str(value)).astimezone().strftime("%d %b %Y  %H:%M:%S")
        except ValueError: return str(value)

    @staticmethod
    def _approach(reason) -> str:
        value = str(reason or "").rsplit(" ", 1)[-1].upper()
        return value.title() if value in {"NORTH", "SOUTH", "EAST", "WEST"} else "—"


class SystemHealthPage(QWidget):
    def __init__(self, repository: Repository) -> None:
        super().__init__()
        self.repository = repository
        root = QVBoxLayout(self); root.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.XL); root.setSpacing(Space.LG)
        root.addLayout(page_header("System Health", "Live software, connectivity, storage and safety diagnostics."))
        grid = QGridLayout(); grid.setSpacing(Space.MD)
        self.metrics = {
            "mqtt": MetricCard("MQTT broker", "Connecting"), "device": MetricCard("Android device", "No device"),
            "gps": MetricCard("Last GPS packet", "No data"), "frequency": MetricCard("GPS frequency", "—"),
            "database": MetricCard("Database", "Checking"), "uptime": MetricCard("Application uptime", "0 s"),
            "temperature": MetricCard("CPU temperature", "Unavailable"), "cpu": MetricCard("CPU usage", "Unavailable"),
            "memory": MetricCard("Memory usage", "Unavailable"), "disk": MetricCard("Disk usage", "—"),
            "safety": MetricCard("Safety state", "Normal"),
        }
        for index, card in enumerate(self.metrics.values()): grid.addWidget(card, index // 4, index % 4)
        root.addLayout(grid)
        warnings = SectionCard("Recent warnings", "Rejected packets, connection loss and safety events from SQLite.")
        self.warning_list = QVBoxLayout(); warnings.body.addLayout(self.warning_list)
        root.addWidget(warnings, 1)

    def refresh(self, mqtt_state: str, device_state: str, last_packet: datetime | None, packet_hz: float | None, uptime: float, safety_state: str) -> None:
        self.metrics["mqtt"].set_value(mqtt_state.title())
        self.metrics["device"].set_value(device_state)
        self.metrics["gps"].set_value(last_packet.astimezone().strftime("%H:%M:%S") if last_packet else "No data")
        self.metrics["frequency"].set_value(f"{packet_hz:.2f} Hz" if packet_hz else "No stream")
        ok, message = self.repository.health_check(); self.metrics["database"].set_value("Healthy" if ok else f"Unavailable: {message}")
        total = int(uptime); self.metrics["uptime"].set_value(f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}")
        self.metrics["safety"].set_value(safety_state.replace("_", " ").title())
        total_disk, used_disk, _free = shutil.disk_usage(Path.cwd()); self.metrics["disk"].set_value(f"{used_disk / total_disk * 100:.0f}%")
        temperature = Path("/sys/class/thermal/thermal_zone0/temp")
        if temperature.exists():
            try: self.metrics["temperature"].set_value(f"{float(temperature.read_text().strip()) / 1000:.1f} °C")
            except (OSError, ValueError): pass
        try:
            import psutil  # type: ignore
            self.metrics["cpu"].set_value(f"{psutil.cpu_percent():.0f}%")
            self.metrics["memory"].set_value(f"{psutil.virtual_memory().percent:.0f}%")
        except ImportError:
            self.metrics["cpu"].set_value("Unavailable")
            self.metrics["memory"].set_value("Unavailable")
        while self.warning_list.count():
            child = self.warning_list.takeAt(0).widget()
            if child: child.deleteLater()
        rows = self.repository.recent_warnings()
        if not rows:
            label = QLabel("No recent warnings. All monitored software systems are nominal."); label.setObjectName("Supporting"); self.warning_list.addWidget(label)
        else:
            for row in rows:
                label = QLabel(f"{str(row['timestamp'])[11:19]}  {str(row['event_type']).replace('_', ' ').title()} — {row['reason']}")
                label.setWordWrap(True); self.warning_list.addWidget(label)


class SettingsPage(QWidget):
    settings_applied = Signal(dict)

    def __init__(self, config: JunctionConfig) -> None:
        super().__init__()
        self.config = config
        root = QVBoxLayout(self); root.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.XL); root.setSpacing(Space.LG)
        root.addLayout(page_header("Settings", "Validated junction configuration. Signal timing changes require explicit confirmation."))
        scroll = QScrollArea(); scroll.setObjectName("PageScroll"); scroll.setWidgetResizable(True)
        body = QWidget(); grid = QGridLayout(body); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(Space.LG)
        self.fields: dict[str, QWidget] = {}
        junction = SectionCard("Junction identity and geofence")
        junction_form = QFormLayout(); junction_form.setSpacing(Space.MD)
        self._line(junction_form, "junction.id", "Junction ID", str(config.junction["id"]))
        self._line(junction_form, "junction.name", "Junction name", str(config.junction["name"]))
        self._double(junction_form, "junction.latitude", "Latitude", float(config.junction["latitude"]), -90, 90, " °")
        self._double(junction_form, "junction.longitude", "Longitude", float(config.junction["longitude"]), -180, 180, " °")
        self._double(junction_form, "detection.activation_radius_metres", "Activation radius", float(config.detection["activation_radius_metres"]), 50, 5000, " m")
        self._double(junction_form, "detection.exit_radius_metres", "Exit radius", float(config.detection["exit_radius_metres"]), 5, 500, " m")
        self._double(junction_form, "detection.maximum_accuracy_metres", "GPS accuracy limit", float(config.detection["maximum_accuracy_metres"]), 1, 250, " m")
        self._double(junction_form, "detection.maximum_packet_age_seconds", "GPS timeout", float(config.detection["maximum_packet_age_seconds"]), 1, 120, " s")
        self._double(junction_form, "detection.heading_tolerance_degrees", "Heading tolerance", float(config.detection["heading_tolerance_degrees"]), 5, 180, " °")
        junction.body.addLayout(junction_form)
        timing = SectionCard("Signal timing", "These values affect the existing safety state machine; no conflicting-green control is exposed.")
        timing_form = QFormLayout(); timing_form.setSpacing(Space.MD)
        self._double(timing_form, "timing.normal_green_seconds", "Normal green", float(config.timing["normal_green_seconds"]), 2, 300, " s")
        self._double(timing_form, "timing.yellow_seconds", "Yellow", float(config.timing["yellow_seconds"]), 1, 30, " s")
        self._double(timing_form, "timing.all_red_seconds", "All-red", float(config.timing["all_red_seconds"]), 0.5, 30, " s")
        self._double(timing_form, "timing.maximum_ambulance_green_seconds", "Maximum emergency green", float(config.timing["maximum_ambulance_green_seconds"]), 5, 300, " s")
        timing.body.addLayout(timing_form)
        connection = SectionCard("Connectivity and simulation")
        connection_form = QFormLayout(); connection_form.setSpacing(Space.MD)
        self._line(connection_form, "mqtt.broker", "MQTT broker", str(config.mqtt["broker"]))
        self._spin(connection_form, "mqtt.port", "MQTT port", int(config.mqtt["port"]), 1, 65535)
        self._double(connection_form, "simulation.speed_multiplier", "Simulation speed", float(config.simulation["speed_multiplier"]), 0.1, 20, " ×")
        connection.body.addLayout(connection_form)
        grid.addWidget(junction, 0, 0); grid.addWidget(timing, 0, 1); grid.addWidget(connection, 1, 0, 1, 2)
        scroll.setWidget(body); root.addWidget(scroll, 1)
        footer = QHBoxLayout(); self.error = QLabel(); self.error.setStyleSheet(f"color:{Color.AMBER};"); footer.addWidget(self.error); footer.addStretch()
        apply_button = PrimaryButton("Validate and apply settings"); apply_button.clicked.connect(self._apply); footer.addWidget(apply_button); root.addLayout(footer)

    def _line(self, layout: QFormLayout, key: str, label: str, value: str) -> None:
        field = QLineEdit(value); self.fields[key] = field; layout.addRow(label, field)

    def _double(self, layout: QFormLayout, key: str, label: str, value: float, low: float, high: float, suffix: str) -> None:
        field = QDoubleSpinBox(); field.setRange(low, high); field.setDecimals(6 if "latitude" in key or "longitude" in key else 1); field.setValue(value); field.setSuffix(suffix)
        self.fields[key] = field; layout.addRow(label, field)

    def _spin(self, layout: QFormLayout, key: str, label: str, value: int, low: int, high: int) -> None:
        field = QSpinBox(); field.setRange(low, high); field.setValue(value); self.fields[key] = field; layout.addRow(label, field)

    def _value(self, key: str):
        field = self.fields[key]
        return field.text().strip() if isinstance(field, QLineEdit) else field.value()

    def _apply(self) -> None:
        values = {key: self._value(key) for key in self.fields}
        if not values["junction.id"] or not values["junction.name"] or not values["mqtt.broker"]:
            self.error.setText("Junction identity and MQTT broker cannot be empty."); return
        if values["detection.exit_radius_metres"] >= values["detection.activation_radius_metres"]:
            self.error.setText("Exit radius must be smaller than the activation radius."); return
        timing_changed = any(float(values[f"timing.{key}"]) != float(self.config.timing[key]) for key in (
            "normal_green_seconds", "yellow_seconds", "all_red_seconds", "maximum_ambulance_green_seconds"))
        if timing_changed and not ConfirmationDialog.confirm(self, "Apply signal timing", "Apply these timing values to the software signal state machine? Existing safety validation remains active.", "Apply timing"):
            return
        self.error.clear(); self.settings_applied.emit(values)
