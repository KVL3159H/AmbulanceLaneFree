"""Live telemetry/status information panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel

from ..core.models import GPSAssessment
from ..core.signal_controller import SignalController


class InformationPanel(QGroupBox):
    FIELD_NAMES = [
        ("mqtt", "MQTT connection"), ("gps", "GPS connection"),
        ("ambulance", "Ambulance ID"), ("trip", "Trip ID"),
        ("priority", "Patient priority"), ("condition", "Reported condition"),
        ("destination", "Destination hospital"), ("latitude", "Latitude"),
        ("longitude", "Longitude"), ("accuracy", "GPS accuracy"),
        ("speed", "Speed"), ("heading", "Heading"),
        ("distance", "Distance"), ("eta", "Calculated ETA"),
        ("approach", "Detected approach"), ("approaching", "Approaching"),
        ("signal", "Current signal state"), ("preemption", "Preemption state"),
        ("selected", "Selected ambulance"), ("waiting", "Waiting ambulances"),
    ]

    def __init__(self) -> None:
        super().__init__("Live status")
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setVerticalSpacing(3)
        self.values: dict[str, QLabel] = {}
        for key, label in self.FIELD_NAMES:
            value = QLabel("—")
            value.setTextInteractionFlags(value.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setStyleSheet("color:#e2e8f0;")
            layout.addRow(label + ":", value)
            self.values[key] = value
        self.values["mqtt"].setText("DISCONNECTED")
        self.values["gps"].setText("NO DATA")

    def set_mqtt_state(self, state: str) -> None:
        self.values["mqtt"].setText(state)

    def update_assessment(self, result: GPSAssessment) -> None:
        packet = result.packet
        values = {
            "gps": "VALID" if result.valid else f"REJECTED: {result.reason}",
            "ambulance": packet.ambulance_id,
            "trip": packet.trip_id,
            "priority": packet.patient_priority.value,
            "condition": packet.patient_condition.replace("_", " ").title(),
            "destination": packet.destination_hospital,
            "latitude": f"{packet.latitude:.6f}",
            "longitude": f"{packet.longitude:.6f}",
            "accuracy": f"{packet.accuracy_metres:.1f} m",
            "speed": f"{packet.speed_mps:.1f} m/s",
            "heading": f"{packet.heading_degrees:.0f}°",
            "distance": f"{result.distance_metres:.1f} m" if result.distance_metres is not None else "—",
            "eta": f"{result.eta_seconds:.1f} s" if result.eta_seconds is not None else "Unavailable",
            "approach": result.approach.value if result.approach else "—",
            "approaching": "YES" if result.approaching else "NO",
        }
        for key, value in values.items():
            self.values[key].setText(value)

    def update_controller(self, controller: SignalController, waiting: int) -> None:
        self.values["signal"].setText(
            " / ".join(f"{side.value[0]}:{colour.value[0]}" for side, colour in controller.signals.items())
        )
        self.values["preemption"].setText(controller.state.value)
        self.values["selected"].setText(controller.target_trip_id or "—")
        self.values["waiting"].setText(str(waiting))
