"""Deterministic, starvation-resistant ambulance request ordering."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import GPSAssessment, PriorityRequest, RequestStatus


class PriorityManager:
    def __init__(self, waiting_protection_seconds: float = 30.0) -> None:
        self.waiting_protection_seconds = max(1.0, waiting_protection_seconds)
        self._requests: dict[str, PriorityRequest] = {}

    def add_or_update(self, assessment: GPSAssessment, now: datetime | None = None) -> PriorityRequest:
        if not assessment.eligible or assessment.approach is None or assessment.distance_metres is None:
            raise ValueError("only eligible GPS assessments may enter the priority queue")
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        packet = assessment.packet
        request = self._requests.get(packet.trip_id)
        if request is None:
            request = PriorityRequest(
                ambulance_id=packet.ambulance_id,
                trip_id=packet.trip_id,
                approach=assessment.approach,
                priority=packet.patient_priority,
                condition=packet.patient_condition,
                destination=packet.destination_hospital,
                distance_metres=assessment.distance_metres,
                eta_seconds=assessment.eta_seconds,
                first_requested_at=now,
                last_updated_at=now,
            )
            self._requests[packet.trip_id] = request
        else:
            if request.status is not RequestStatus.ACTIVE:
                request.approach = assessment.approach
            request.priority = packet.patient_priority
            request.distance_metres = assessment.distance_metres
            request.eta_seconds = assessment.eta_seconds
            request.last_updated_at = now
            request.condition = packet.patient_condition
            request.destination = packet.destination_hospital
        return request

    def remove(self, trip_id: str, status: RequestStatus = RequestStatus.CANCELLED) -> PriorityRequest | None:
        request = self._requests.pop(trip_id, None)
        if request:
            request.status = status
        return request

    def get(self, trip_id: str) -> PriorityRequest | None:
        return self._requests.get(trip_id)

    def ordered(self, now: datetime | None = None) -> list[PriorityRequest]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        def key(request: PriorityRequest) -> tuple[float | int | str, ...]:
            wait = max(0.0, (now - request.first_requested_at).total_seconds())
            aging_steps = int(wait // self.waiting_protection_seconds)
            effective_medical_rank = max(0, request.priority.rank - aging_steps)
            eta = request.eta_seconds if request.eta_seconds is not None else float("inf")
            return (
                0 if request.inside_junction else 1,
                effective_medical_rank,
                eta,
                -wait,
                request.ambulance_id,
            )

        return sorted(self._requests.values(), key=key)

    def next_request(self, now: datetime | None = None) -> PriorityRequest | None:
        ordered = self.ordered(now)
        return ordered[0] if ordered else None

    def __len__(self) -> int:
        return len(self._requests)

    def clear(self) -> None:
        self._requests.clear()

    def mark_active(self, trip_id: str) -> PriorityRequest | None:
        request = self._requests.get(trip_id)
        if request:
            request.status = RequestStatus.ACTIVE
        return request
