"""Current signal and active-emergency presentation cards."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core.models import GPSAssessment, PriorityRequest
from ..core.signal_controller import SignalController
from ..core.signal_states import PreemptionState
from .components import EmptyState, PriorityBadge, StatusBadge
from .theme import Color, Space


class ValueRow(QWidget):
    def __init__(self, label: str, value: str = "—") -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.SM)
        caption = QLabel(label)
        caption.setObjectName("Supporting")
        self.value = QLabel(value)
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value.setWordWrap(True)
        layout.addWidget(caption, 1)
        layout.addWidget(self.value, 2)


class CurrentSignalCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        root = QVBoxLayout(self)
        root.setContentsMargins(Space.LG, Space.LG, Space.LG, Space.LG)
        root.setSpacing(Space.MD)
        title = QHBoxLayout()
        heading = QLabel("Current signal")
        heading.setObjectName("CardTitle")
        self.badge = StatusBadge("Normal operation", "success")
        title.addWidget(heading)
        title.addStretch()
        title.addWidget(self.badge)
        root.addLayout(title)
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(Space.LG)
        metrics.setVerticalSpacing(Space.SM)
        self.phase = ValueRow("Active phase", "All-red clearance")
        self.machine = ValueRow("State machine", "Normal")
        self.remaining = ValueRow("Remaining timer", "—")
        self.selected = ValueRow("Selected ambulance")
        self.direction = ValueRow("Priority direction")
        for index, row in enumerate((self.phase, self.machine, self.remaining, self.selected, self.direction)):
            metrics.addWidget(row, index, 0)
        root.addLayout(metrics)
        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        self.explanation.setStyleSheet(f"color:{Color.RED}; font-weight:600;")
        self.explanation.setAccessibleName("Fail-safe explanation")
        self.explanation.hide()
        root.addWidget(self.explanation)

    def update_controller(self, controller: SignalController, remaining: float | None, selected_request: PriorityRequest | None = None) -> None:
        state = controller.state
        labels = {
            PreemptionState.NORMAL: ("Normal operation", "success"),
            PreemptionState.REQUEST_VALIDATION: ("Validating request", "info"),
            PreemptionState.PREEMPTION_PENDING: ("Priority pending", "warning"),
            PreemptionState.CLEAR_CURRENT_GREEN: ("Clearance pending", "warning"),
            PreemptionState.ALL_RED_CLEARANCE: ("All-red clearance", "warning"),
            PreemptionState.AMBULANCE_GREEN: ("Priority active", "critical"),
            PreemptionState.PASSAGE_MONITORING: ("Priority active", "critical"),
            PreemptionState.RECOVERY_YELLOW: ("Restoring normal", "warning"),
            PreemptionState.RECOVERY_ALL_RED: ("Restoring normal", "warning"),
            PreemptionState.RETURN_TO_NORMAL: ("Restoring normal", "info"),
            PreemptionState.FAIL_SAFE: ("Fail-safe active", "critical"),
        }
        badge, tone = labels[state]
        self.badge.set_status(badge, tone, f"Preemption state: {state.value}")
        self.phase.value.setText(controller.normal_phase.value.replace("_", " ").title() if state is PreemptionState.NORMAL else badge)
        self.machine.value.setText(state.value.replace("_", " ").title())
        self.remaining.value.setText(f"{remaining:.1f} s" if remaining is not None else "Monitoring")
        self.selected.value.setText(selected_request.ambulance_id if selected_request else "None")
        self.direction.value.setText(controller.target_approach.value.title() if controller.target_approach else "None")
        if state is PreemptionState.FAIL_SAFE:
            self.explanation.setText("Safety invariant triggered. Every approach is forced red and timing is paused until a controlled reset.")
            self.explanation.show()
        else:
            self.explanation.hide()


class ActiveEmergencyCard(QFrame):
    FIELDS = [
        ("ambulance", "Ambulance"), ("trip", "Trip ID"), ("condition", "Condition"),
        ("approach", "Approach"), ("distance", "Distance"), ("eta", "ETA"),
        ("speed", "Speed"), ("accuracy", "GPS accuracy"), ("destination", "Destination"),
        ("request", "Request status"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        self.setStyleSheet(f"QFrame#SectionCard {{ border-left: 4px solid {Color.DISABLED}; }}")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(Space.LG, Space.LG, Space.LG, Space.LG)
        self.root.setSpacing(Space.SM)
        title = QHBoxLayout()
        heading = QLabel("Active emergency")
        heading.setObjectName("CardTitle")
        self.priority = PriorityBadge("No priority")
        title.addWidget(heading); title.addStretch(); title.addWidget(self.priority)
        self.root.addLayout(title)
        self.empty = EmptyState("No active emergency", "Waiting for a valid GPS request from an authorized ambulance.")
        self.root.addWidget(self.empty)
        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(Space.XS)
        self.rows: dict[str, ValueRow] = {}
        for key, label in self.FIELDS:
            row = ValueRow(label)
            self.rows[key] = row
            content_layout.addWidget(row)
        self.root.addWidget(self.content)
        self.content.hide()

    def update_assessment(self, result: GPSAssessment, request: PriorityRequest | None) -> None:
        packet = result.packet
        self.empty.hide(); self.content.show()
        self.priority.set_priority(packet.patient_priority.value)
        colour = {"RED": Color.RED, "YELLOW": Color.AMBER, "GREEN": Color.GREEN}[packet.patient_priority.value]
        self.setStyleSheet(f"QFrame#SectionCard {{ border-left: 4px solid {colour}; }}")
        values = {
            "ambulance": packet.ambulance_id,
            "trip": packet.trip_id,
            "condition": packet.patient_condition.replace("_", " ").title(),
            "approach": result.approach.value.title() if result.approach else "Not detected",
            "distance": f"{result.distance_metres:.0f} m" if result.distance_metres is not None else "Unavailable",
            "eta": f"{result.eta_seconds:.1f} s" if result.eta_seconds is not None else "Unavailable",
            "speed": f"{packet.speed_mps:.1f} m/s",
            "accuracy": f"{packet.accuracy_metres:.1f} m",
            "destination": packet.destination_hospital,
            "request": request.status.value.replace("_", " ").title() if request else result.reason,
        }
        for key, value in values.items(): self.rows[key].value.setText(value)

    def show_gps_loss(self) -> None:
        if self.content.isVisible():
            self.rows["request"].value.setText("GPS lost — safe timeout active")

    def clear_active(self) -> None:
        self.content.hide(); self.empty.show(); self.setStyleSheet(f"QFrame#SectionCard {{ border-left: 4px solid {Color.DISABLED}; }}")
