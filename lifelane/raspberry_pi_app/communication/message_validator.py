"""Strict JSON-to-domain conversion used by MQTT and tests."""

from __future__ import annotations

import json

from ..core.models import TelemetryPacket

REQUIRED_FIELDS = {
    "schemaVersion",
    "sequenceNumber",
    "ambulanceId",
    "tripId",
    "latitude",
    "longitude",
    "accuracyMetres",
    "speedMps",
    "headingDegrees",
    "patientPriority",
    "patientCondition",
    "destinationHospital",
    "emergencyActive",
    "timestamp",
}

ALLOWED_CONDITIONS = {
    "CARDIAC", "BREATHING", "UNCONSCIOUS", "SEVERE_BLEEDING", "TRAUMA",
    "PREGNANCY", "STROKE", "BURNS", "OTHER",
}


class InvalidMessage(ValueError):
    pass


def validate_telemetry_payload(payload: bytes | str) -> TelemetryPacket:
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise InvalidMessage("payload must be a JSON object")
        missing = REQUIRED_FIELDS.difference(data)
        if missing:
            raise InvalidMessage(f"missing fields: {', '.join(sorted(missing))}")
        packet = TelemetryPacket.from_dict(data)
        if packet.sequence_number < 0:
            raise InvalidMessage("sequenceNumber must be non-negative")
        if len(packet.patient_condition) > 64 or len(packet.destination_hospital) > 120:
            raise InvalidMessage("text field is too long")
        if packet.patient_condition not in ALLOWED_CONDITIONS:
            raise InvalidMessage("unsupported patient condition category")
        return packet
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        if isinstance(exc, InvalidMessage):
            raise
        raise InvalidMessage(str(exc)) from exc
