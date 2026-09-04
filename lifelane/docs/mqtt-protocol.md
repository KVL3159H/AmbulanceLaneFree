# MQTT protocol

All messages are UTF-8 JSON. Emergency, cancel, ambulance/junction status, and events use QoS 1. Telemetry also uses QoS 1 in this prototype. Paho and HiveMQ clients reconnect automatically. Retained status plus a last-will message exposes disconnection.

## Topics

```text
lifelane/ambulance/{ambulanceId}/telemetry
lifelane/ambulance/{ambulanceId}/emergency
lifelane/ambulance/{ambulanceId}/cancel
lifelane/ambulance/{ambulanceId}/status
lifelane/junction/{junctionId}/request
lifelane/junction/{junctionId}/status
lifelane/junction/{junctionId}/events
```

The junction subscribes to all ambulance telemetry/emergency/cancel topics and publishes retained junction status plus event messages. `{ambulanceId}` must also be present in `config/junction.yaml`.

## Telemetry schema version 1

```json
{
  "schemaVersion": 1,
  "sequenceNumber": 101,
  "ambulanceId": "AMB-001",
  "tripId": "TRIP-1001",
  "latitude": 9.454,
  "longitude": 77.5535,
  "accuracyMetres": 8.0,
  "speedMps": 12.5,
  "headingDegrees": 180.0,
  "patientPriority": "RED",
  "patientCondition": "CARDIAC",
  "destinationHospital": "Government Hospital",
  "emergencyActive": true,
  "timestamp": "2026-09-04T10:30:20Z"
}
```

Supported condition codes are `CARDIAC`, `BREATHING`, `UNCONSCIOUS`, `SEVERE_BLEEDING`, `TRAUMA`, `PREGNANCY`, `STROKE`, `BURNS`, and `OTHER`. They are reported categories, not diagnoses.

Emergency lifecycle and cancel messages include `schemaVersion`, `sequenceNumber`, `ambulanceId`, `tripId`, `emergencyActive`, and an ISO-8601 UTC `timestamp`. Telemetry duplicate detection is per ambulance/trip and rejects non-increasing sequence numbers. The junction rejects packets older than the configured maximum, more than two seconds in the future, inaccurate beyond the threshold, inactive, invalid, or unauthorized.

## Credentials

Desktop credentials are read from `LIFELANE_MQTT_USERNAME` and `LIFELANE_MQTT_PASSWORD` in an external `.env`. Android values come from ignored `android_app/local.properties`. No real credential is committed. The prototype listener is plain MQTT; use mutually authenticated TLS and device-specific credentials for anything beyond an isolated demonstration LAN.
