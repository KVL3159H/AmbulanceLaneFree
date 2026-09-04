"""Parameterized persistence operations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..core.models import TelemetryPacket


class Repository:
    def __init__(self, connection: sqlite3.Connection, junction_id: str) -> None:
        self.connection = connection
        self.junction_id = junction_id

    def record_packet(self, packet: TelemetryPacket) -> bool:
        stamp = packet.timestamp.isoformat()
        with self.connection:
            self.connection.execute(
                """INSERT INTO ambulances
                   (ambulance_id, display_name, authorized, last_connection, last_latitude, last_longitude)
                   VALUES (?, ?, 1, ?, ?, ?)
                   ON CONFLICT(ambulance_id) DO UPDATE SET
                     last_connection=excluded.last_connection,
                     last_latitude=excluded.last_latitude,
                     last_longitude=excluded.last_longitude""",
                (packet.ambulance_id, packet.ambulance_id, stamp, packet.latitude, packet.longitude),
            )
            self.connection.execute(
                """INSERT INTO trips
                   (trip_id, ambulance_id, priority, condition, destination, start_time, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(trip_id) DO UPDATE SET
                     priority=excluded.priority, condition=excluded.condition,
                     destination=excluded.destination, status=excluded.status""",
                (
                    packet.trip_id,
                    packet.ambulance_id,
                    packet.patient_priority.value,
                    packet.patient_condition,
                    packet.destination_hospital,
                    stamp,
                    "ACTIVE" if packet.emergency_active else "CANCELLED",
                ),
            )
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO telemetry
                   (trip_id, sequence_number, latitude, longitude, accuracy, speed, heading, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    packet.trip_id,
                    packet.sequence_number,
                    packet.latitude,
                    packet.longitude,
                    packet.accuracy_metres,
                    packet.speed_mps,
                    packet.heading_degrees,
                    stamp,
                ),
            )
        return cursor.rowcount == 1

    def finish_trip(self, trip_id: str, status: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE trips SET end_time=?, status=? WHERE trip_id=?",
                (datetime.now(timezone.utc).isoformat(), status, trip_id),
            )

    def record_signal_event(
        self,
        event_type: str,
        reason: str,
        trip_id: str | None = None,
        previous_state: str | None = None,
        new_state: str | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO signal_events
                   (junction_id, trip_id, event_type, previous_state, new_state, reason, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.junction_id,
                    trip_id,
                    event_type,
                    previous_state,
                    new_state,
                    reason,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
