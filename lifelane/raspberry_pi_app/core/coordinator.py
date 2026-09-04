"""One processing pipeline shared by MQTT telemetry and simulated GPS."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from .config import JunctionConfig
from .gps_engine import GPSEngine
from .models import GPSAssessment, PriorityRequest, RequestStatus, TelemetryPacket
from .passage_detector import PassageDetector
from .priority_manager import PriorityManager
from .signal_controller import SignalController
from .signal_states import PreemptionState
from ..database.repository import Repository

EventCallback = Callable[[str, str], None]


class LifeLaneCoordinator:
    def __init__(
        self,
        config: JunctionConfig,
        repository: Repository | None = None,
        event_callback: EventCallback | None = None,
    ) -> None:
        self.config = config
        self.repository = repository
        self.event_callback = event_callback or (lambda _event, _message: None)
        self.gps = GPSEngine(config)
        self.priority = PriorityManager(float(config.detection.get("waiting_time_protection_seconds", 30)))
        self.passage = PassageDetector(
            float(config.detection["exit_radius_metres"]),
            float(config.detection["heading_tolerance_degrees"]),
        )
        self.controller = SignalController(config, self._controller_event)
        self.latest: dict[str, GPSAssessment] = {}
        self.last_packet_at: dict[str, datetime] = {}
        self.gps_lost_trips: set[str] = set()
        self.completed_trips: set[str] = set()

    def process_packet(self, packet: TelemetryPacket, now: datetime | None = None) -> GPSAssessment:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if not packet.emergency_active:
            self.cancel(packet.trip_id, "Emergency trip inactive")
        assessment = self.gps.assess(packet, now)
        if self.repository and assessment.valid:
            self.repository.record_packet(packet)
        self.latest[packet.trip_id] = assessment
        self.last_packet_at[packet.trip_id] = now
        self.gps_lost_trips.discard(packet.trip_id)
        self._event("GPS_PACKET", f"{packet.ambulance_id} sequence {packet.sequence_number} received")
        if not assessment.valid:
            self._event("REQUEST_REJECTED", assessment.reason)
            return assessment
        if assessment.approach:
            self._event("APPROACH_DETECTED", f"{assessment.approach.value.title()} approach detected")
        if assessment.eligible:
            request = self.priority.add_or_update(assessment, now)
            if assessment.distance_metres <= float(self.config.detection["exit_radius_metres"]):
                request.inside_junction = True
            self._event("REQUEST_ACCEPTED", f"{packet.ambulance_id} accepted at {assessment.distance_metres:.0f} m")
            if packet.trip_id == self.controller.target_trip_id:
                request.status = RequestStatus.ACTIVE
                if self.passage.update(assessment):
                    self.controller.mark_passage_complete(packet.trip_id)
                    self.priority.remove(packet.trip_id, RequestStatus.PASSED)
                    self.completed_trips.add(packet.trip_id)
                    if self.repository:
                        self.repository.finish_trip(packet.trip_id, "DELIVERED_THROUGH_JUNCTION")
                    self._event("AMBULANCE_CROSSED", f"{packet.ambulance_id} crossed junction")
            self._select_if_possible(now)
        else:
            self._event("REQUEST_NOT_ELIGIBLE", assessment.reason)
            # An active vehicle may become ineligible after crossing; passage still needs its samples.
            if packet.trip_id == self.controller.target_trip_id:
                if self.passage.update(assessment):
                    self.controller.mark_passage_complete(packet.trip_id)
                    self.priority.remove(packet.trip_id, RequestStatus.PASSED)
                    self.completed_trips.add(packet.trip_id)
                    self._event("AMBULANCE_CROSSED", f"{packet.ambulance_id} crossed junction")
        return assessment

    def tick(self, seconds: float, now: datetime | None = None) -> None:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        previous_state = self.controller.state
        previous_trip = self.controller.target_trip_id
        self.controller.tick(seconds)
        if (
            previous_trip
            and previous_state is PreemptionState.PASSAGE_MONITORING
            and self.controller.state is PreemptionState.RECOVERY_YELLOW
            and previous_trip not in self.completed_trips
        ):
            self.priority.remove(previous_trip, RequestStatus.REJECTED)
            if self.repository:
                self.repository.finish_trip(previous_trip, "PREEMPTION_TIMEOUT")
        trip_id = self.controller.target_trip_id
        if trip_id and self.controller.state in {
            PreemptionState.AMBULANCE_GREEN,
            PreemptionState.PASSAGE_MONITORING,
        }:
            last = self.last_packet_at.get(trip_id)
            timeout = float(self.config.detection["maximum_packet_age_seconds"])
            if last and (now - last).total_seconds() > timeout and trip_id not in self.gps_lost_trips:
                self.gps_lost_trips.add(trip_id)
                self._event("GPS_CONNECTION_LOST", f"GPS lost for {trip_id}; maximum green timeout remains active")
        if self.controller.state is PreemptionState.NORMAL:
            self._select_if_possible(now)

    def cancel(self, trip_id: str, reason: str = "Emergency trip cancelled") -> None:
        removed = self.priority.remove(trip_id, RequestStatus.CANCELLED)
        if trip_id == self.controller.target_trip_id:
            self.controller.cancel_preemption(trip_id)
        if self.repository:
            self.repository.finish_trip(trip_id, "CANCELLED")
        self._event("EMERGENCY_CANCELLED", f"{trip_id}: {reason}" if removed else reason)

    def reset(self) -> None:
        self.gps.reset()
        self.priority.clear()
        self.passage.reset()
        self.latest.clear()
        self.last_packet_at.clear()
        self.gps_lost_trips.clear()
        self.completed_trips.clear()
        self.controller.reset()

    def _select_if_possible(self, now: datetime) -> None:
        if self.controller.state is not PreemptionState.NORMAL or self.controller.target_trip_id:
            return
        request = self.priority.next_request(now)
        if request and self.controller.request_preemption(request.approach, request.trip_id):
            self.priority.mark_active(request.trip_id)
            self._event("AMBULANCE_SELECTED", f"{request.ambulance_id} selected for {request.approach.value}")

    def _controller_event(self, event_type: str, message: str) -> None:
        self._event(event_type, message)

    def _event(self, event_type: str, message: str) -> None:
        if self.repository:
            self.repository.record_signal_event(
                event_type,
                message,
                trip_id=self.controller.target_trip_id,
                new_state=self.controller.state.value,
            )
        self.event_callback(event_type, message)
