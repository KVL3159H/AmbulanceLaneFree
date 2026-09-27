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
from .protocol import JunctionState
from .event_logger import EventLogger
from ..database.repository import Repository

EventCallback = Callable[[str, str], None]


class LifeLaneCoordinator:
    def __init__(
        self,
        config: JunctionConfig,
        repository: Repository | None = None,
        event_callback: EventCallback | None = None,
        automatic_requests: bool = True,
    ) -> None:
        self.config = config
        self.automatic_requests = automatic_requests
        self.repository = repository
        self.event_callback = event_callback or (lambda _event, _message: None)
        self.events = EventLogger()
        self.event_time = datetime.now(timezone.utc)
        self.gps = GPSEngine(config)
        self.priority = PriorityManager(float(config.detection.get("waiting_time_protection_seconds", 30)))
        self.passage = PassageDetector(
            float(config.detection["exit_radius_metres"]),
            float(config.detection["heading_tolerance_degrees"]),
        )
        self.controller = SignalController(config, self._controller_event)
        self.latest: dict[str, GPSAssessment] = {}
        self.latest_reliable: dict[str, GPSAssessment] = {}
        self.last_packet_at: dict[str, datetime] = {}
        self.gps_lost_trips: set[str] = set()
        self.completed_trips: set[str] = set()
        self._occupancy_uncertain = False
        self._away_counts: dict[str, int] = {}
        self.outcomes: dict[str, str] = {}

    def process_packet(self, packet: TelemetryPacket, now: datetime | None = None) -> GPSAssessment:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.event_time = now
        old = self.latest_reliable.get(packet.trip_id)
        if (old and packet.request_id and old.packet.request_id and packet.request_id != old.packet.request_id
            and self.outcomes.get(packet.trip_id)=="CANCELLED" and self.controller.target_trip_id != packet.trip_id):
            self.gps.reset_trip(packet.ambulance_id,packet.trip_id)
            self.passage.reset(packet.trip_id)
        if not packet.emergency_active:
            self.cancel(packet.trip_id, "Emergency trip inactive")
        assessment = self.gps.assess(packet, now)
        if self.repository and assessment.valid:
            self.repository.record_packet(packet)
        self.latest[packet.trip_id] = assessment
        self._event("GPS_PACKET", f"{packet.ambulance_id} sequence {packet.sequence_number} received", packet.trip_id)
        if not assessment.valid:
            self._event("REQUEST_REJECTED", f"{packet.ambulance_id}: {assessment.reason}", packet.trip_id)
            return assessment
        self.last_packet_at[packet.trip_id] = packet.timestamp
        self.latest_reliable[packet.trip_id] = assessment
        self.gps_lost_trips.discard(packet.trip_id)
        if packet.trip_id in self.completed_trips:
            return assessment
        if assessment.approach:
            self._event("APPROACH_DETECTED", f"{assessment.approach.value.title()} approach detected")
        if assessment.eligible and (self.automatic_requests or self.priority.get(packet.trip_id)):
            first_request = self.priority.get(packet.trip_id) is None
            request = self.priority.add_or_update(assessment, now)
            request.inside_junction = self.passage.entered_zone(packet.trip_id)
            if first_request:
                self._event("REQUEST_ACCEPTED", f"{packet.ambulance_id} accepted at {assessment.route_distance_metres:.0f} m", packet.trip_id)
            if packet.trip_id == self.controller.target_trip_id:
                request.status = RequestStatus.ACTIVE
            self._select_if_possible(now)
        else:
            self._event("REQUEST_NOT_ELIGIBLE", assessment.reason)
            self._away_counts[packet.trip_id] = self._away_counts.get(packet.trip_id, 0) + 1 if assessment.reason == "ambulance is moving away" else 0
            if self._away_counts[packet.trip_id] >= 3 and not self.passage.entered_zone(packet.trip_id):
                if self.priority.get(packet.trip_id):
                    self.cancel(packet.trip_id, "APPROACH_CANCELLED: ambulance turned away")
        # Passage has one path, including after an ambulance is no longer approaching.
        if packet.trip_id == self.controller.target_trip_id:
            entered = self.passage.entered_zone(packet.trip_id)
            cleared = self.passage.update(assessment)
            if not entered and self.passage.entered_zone(packet.trip_id):
                self._event("JUNCTION_ENTERED", "Stop-line crossing confirmed by repeated samples", packet.trip_id)
            if cleared:
                self.controller.mark_passage_complete(packet.trip_id)
                self.priority.remove(packet.trip_id, RequestStatus.PASSED)
                self.completed_trips.add(packet.trip_id)
                self.outcomes[packet.trip_id] = "JUNCTION_CLEARED"
                self._event("JUNCTION_CLEARED", "Validated exit passage", packet.trip_id)
                if self.repository:
                    self.repository.finish_trip(packet.trip_id, "DELIVERED_THROUGH_JUNCTION")
                self._event("AMBULANCE_CROSSED", f"{packet.ambulance_id} crossed junction", packet.trip_id)
        request = self.priority.get(packet.trip_id)
        if request:
            request.inside_junction = self.passage.entered_zone(packet.trip_id)
        return assessment

    def tick(self, seconds: float, now: datetime | None = None) -> None:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.event_time = now
        previous_state = self.controller.state
        previous_trip = self.controller.target_trip_id
        if (previous_trip and self.passage.entered_zone(previous_trip)
            and previous_trip not in self.completed_trips
            and previous_state is PreemptionState.PASSAGE_MONITORING
            and self.controller.elapsed + seconds >= float(self.config.timing["maximum_ambulance_green_seconds"])):
            self._occupancy_uncertain = True
        self.controller.tick(seconds)
        if previous_trip and previous_state is PreemptionState.RETURN_TO_NORMAL and self.controller.state is PreemptionState.NORMAL:
            self._event("NORMAL_RESTORED", "Normal cycle restored", previous_trip)
        if self._occupancy_uncertain and self.controller.state is PreemptionState.RECOVERY_ALL_RED:
            self.controller._enter_fail_safe("Junction occupancy unknown after maximum green; controlled recovery required")
        if (
            previous_trip
            and previous_state is PreemptionState.PASSAGE_MONITORING
            and self.controller.state is PreemptionState.RECOVERY_YELLOW
            and previous_trip not in self.completed_trips
        ):
            self.priority.remove(previous_trip, RequestStatus.REJECTED)
            self.completed_trips.add(previous_trip)
            self.outcomes[previous_trip] = "REQUEST_REJECTED"
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
        if self.passage.entered_zone(trip_id) and trip_id not in self.completed_trips:
            self._event("CANCELLATION_DEFERRED", "Ambulance occupies junction; clearance or safety timeout required")
            return
        self.completed_trips.add(trip_id)
        self.outcomes[trip_id] = "CANCELLED"
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
        self.latest_reliable.clear()
        self.last_packet_at.clear()
        self.gps_lost_trips.clear()
        self.completed_trips.clear()
        self._occupancy_uncertain = False
        self._away_counts.clear()
        self.outcomes.clear()
        self.controller.reset()

    def _select_if_possible(self, now: datetime) -> None:
        if self.controller.state is not PreemptionState.NORMAL or self.controller.target_trip_id:
            return
        for pending in self.priority.ordered(now):
            if (now - pending.last_updated_at).total_seconds() > float(self.config.detection["maximum_packet_age_seconds"]):
                self.priority.remove(pending.trip_id, RequestStatus.REJECTED)
                self.completed_trips.add(pending.trip_id)
                self.outcomes[pending.trip_id] = "REQUEST_REJECTED"
                self._event("REQUEST_EXPIRED", pending.trip_id)
        request = self.priority.next_request(now)
        if request and self.controller.request_preemption(request.approach, request.trip_id):
            self.priority.mark_active(request.trip_id)
            self._event("AMBULANCE_SELECTED", f"{request.ambulance_id} selected for {request.approach.value}")

    def junction_state(self, trip_id: str) -> JunctionState:
        """One canonical projection of controller, request and validated GPS evidence."""
        state = self.controller.state
        if state is PreemptionState.FAIL_SAFE:
            return JunctionState.FAIL_SAFE
        outcome = self.outcomes.get(trip_id)
        if outcome in {"CANCELLED", "REQUEST_REJECTED"}:
            return JunctionState(outcome)
        active = self.controller.target_trip_id == trip_id
        if outcome == "JUNCTION_CLEARED":
            if active:
                return JunctionState.NORMAL_RESTORING if state in {PreemptionState.RECOVERY_YELLOW, PreemptionState.RECOVERY_ALL_RED, PreemptionState.RETURN_TO_NORMAL} else JunctionState.JUNCTION_CLEARED
            return JunctionState.COMPLETED
        assessment = self.latest_reliable.get(trip_id)
        if active:
            if state is PreemptionState.REQUEST_VALIDATION:
                return JunctionState.PRIORITY_REQUESTED
            if state is PreemptionState.PREEMPTION_PENDING:
                return JunctionState.CONTROLLER_VALIDATED
            if state in {PreemptionState.CLEAR_CURRENT_GREEN, PreemptionState.ALL_RED_CLEARANCE}:
                return JunctionState.SAFE_TRANSITION
            if self.passage.entered_zone(trip_id):
                if assessment and not assessment.inside_polygon and (assessment.after_exit_metres or 0) > 0:
                    return JunctionState.EXIT_CONFIRMING
                if self.passage.entry_confirmations(trip_id) == 2:
                    return JunctionState.STOP_LINE_CROSSED
                return JunctionState.INSIDE_JUNCTION
            if state in {PreemptionState.AMBULANCE_GREEN, PreemptionState.PASSAGE_MONITORING}:
                return JunctionState.PRIORITY_GREEN
        if self.priority.get(trip_id):
            return JunctionState.CONTROLLER_VALIDATED
        if assessment is None or (assessment.distance_metres or 0) > self.config.detection.get("monitoring_distance_metres", 1000):
            return JunctionState.OUTSIDE_COVERAGE
        if assessment.eligible:
            return JunctionState.APPROACH_CONFIRMED
        return JunctionState.APPROACH_CONFIRMING

    def _controller_event(self, event_type: str, message: str) -> None:
        self._event(event_type, message)

    def _event(self, event_type: str, message: str, event_trip_id: str | None = None) -> None:
        trip = event_trip_id if event_trip_id is not None else self.controller.target_trip_id
        assessment = self.latest_reliable.get(trip) if hasattr(self, "latest_reliable") else None
        self.events.record(timestamp=self.event_time.isoformat(),sourceComponent="junction_controller",
            eventType=event_type,tripId=trip,junctionId=self.config.junction["id"],
            requestId=assessment.packet.request_id if assessment else None,
            ambulanceId=assessment.packet.ambulance_id if assessment else None,
            approachSide=assessment.approach.value if assessment and assessment.approach else None,
            gpsAccuracy=assessment.packet.accuracy_metres if assessment else None,
            distanceToStopLine=assessment.route_distance_metres if assessment else None,
            controllerState=self.controller.state.value,
            signalState={s.value:c.value for s,c in self.controller.signals.items()},result=message,
            failureReason=message if any(token in event_type for token in ("REJECTED","ERROR","FAIL","LOST")) else None)
        if self.repository:
            self.repository.record_signal_event(
                event_type,
                message,
                trip_id=event_trip_id if event_trip_id is not None else self.controller.target_trip_id,
                new_state=self.controller.state.value,
            )
        self.event_callback(event_type, message)
