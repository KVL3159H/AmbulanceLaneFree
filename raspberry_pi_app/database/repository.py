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

    def list_trips(self, search: str = "", status: str = "", priority: str = "", limit: int = 250):
        clauses: list[str] = []
        values: list[object] = []
        if search:
            clauses.append("(t.trip_id LIKE ? OR t.ambulance_id LIKE ? OR t.destination LIKE ? OR t.condition LIKE ?)")
            token = f"%{search}%"
            values.extend([token, token, token, token])
        if status:
            clauses.append("t.status = ?")
            values.append(status)
        if priority:
            clauses.append("t.priority = ?")
            values.append(priority)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(limit, 1000)))
        return self.connection.execute(
            f"""SELECT t.*,
                (SELECT MIN(timestamp) FROM signal_events s WHERE s.trip_id=t.trip_id AND s.event_type='AMBULANCE_GREEN') AS green_time,
                (SELECT MIN(timestamp) FROM signal_events s WHERE s.trip_id=t.trip_id AND s.event_type='AMBULANCE_SELECTED') AS selected_time,
                (SELECT reason FROM signal_events s WHERE s.trip_id=t.trip_id AND s.event_type='AMBULANCE_SELECTED'
                 ORDER BY timestamp ASC LIMIT 1) AS selected_reason
                FROM trips t {where} ORDER BY t.start_time DESC LIMIT ?""",
            values,
        ).fetchall()

    def recent_warnings(self, limit: int = 8):
        return self.connection.execute(
            """SELECT event_type, reason, timestamp FROM signal_events
               WHERE event_type LIKE '%ERROR%' OR event_type LIKE '%LOST%'
                  OR event_type LIKE '%REJECTED%' OR event_type LIKE '%CRITICAL%'
               ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    def recent_request_outcomes(self, limit: int = 40) -> list[dict[str, object]]:
        """Return completed/cancelled trips and GPS-rejected request attempts."""
        completed = [dict(row) for row in self.connection.execute(
            """SELECT t.trip_id, t.ambulance_id, t.priority, t.status AS outcome,
                      COALESCE(t.end_time, t.start_time) AS occurred, '' AS reason,
                      (SELECT MIN(timestamp) FROM signal_events s WHERE s.trip_id=t.trip_id AND s.event_type='AMBULANCE_GREEN') AS green_time,
                      (SELECT MIN(timestamp) FROM signal_events s WHERE s.trip_id=t.trip_id AND s.event_type='AMBULANCE_SELECTED') AS selected_time,
                      (SELECT reason FROM signal_events s WHERE s.trip_id=t.trip_id AND s.event_type='AMBULANCE_SELECTED'
                       ORDER BY timestamp ASC LIMIT 1) AS selected_reason
               FROM trips t WHERE t.status <> 'ACTIVE' ORDER BY occurred DESC LIMIT ?""",
            (limit,),
        ).fetchall()]
        rejected = [dict(row) for row in self.connection.execute(
            """SELECT COALESCE(e.trip_id, '—') AS trip_id,
                      CASE WHEN instr(e.reason, ':') > 0 THEN substr(e.reason, 1, instr(e.reason, ':') - 1) ELSE 'Unknown' END AS ambulance_id,
                      COALESCE(t.priority, '—') AS priority, 'REJECTED' AS outcome,
                      e.timestamp AS occurred, e.reason AS reason, NULL AS green_time,
                      NULL AS selected_time, NULL AS selected_reason
               FROM signal_events e LEFT JOIN trips t ON t.trip_id=e.trip_id
               WHERE e.event_type='REQUEST_REJECTED' ORDER BY e.timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()]
        return sorted(completed + rejected, key=lambda row: str(row.get("occurred") or ""), reverse=True)[:limit]

    def health_check(self) -> tuple[bool, str]:
        try:
            result = self.connection.execute("PRAGMA quick_check").fetchone()
            message = str(result[0]) if result else "No result"
            return message.lower() == "ok", message
        except Exception as exc:  # pragma: no cover - depends on external database state
            return False, str(exc)
