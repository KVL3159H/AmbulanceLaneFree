"""Paho MQTT adapter with reconnection, QoS 1, TLS/credential env support and LWT."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from ..core.config import JunctionConfig
from ..core.models import TelemetryPacket, parse_timestamp
from .message_validator import InvalidMessage, validate_telemetry_payload
from .topics import (
    ambulance_cancel, ambulance_emergency, ambulance_status, ambulance_telemetry,
    junction_events, junction_request, junction_status,
)


class MQTTClient:
    def __init__(
        self,
        config: JunctionConfig,
        packet_callback: Callable[[TelemetryPacket], None],
        cancel_callback: Callable[[str], None],
        state_callback: Callable[[str], None],
        error_callback: Callable[[str], None],
        status_callback: Callable[[str, bool], None] | None = None,
    ) -> None:
        self.config = config
        self.packet_callback = packet_callback
        self.cancel_callback = cancel_callback
        self.state_callback = state_callback
        self.error_callback = error_callback
        self.status_callback = status_callback
        self._lock = threading.Lock()
        self._lifecycle_sequences: dict[tuple[str, str], int] = {}
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"lifelane-junction-{config.junction['id']}",
            clean_session=True,
        )
        username = os.getenv("LIFELANE_MQTT_USERNAME")
        password = os.getenv("LIFELANE_MQTT_PASSWORD")
        if username:
            self.client.username_pw_set(username, password)
        if os.getenv("LIFELANE_MQTT_TLS", "false").lower() in {"1", "true", "yes"}:
            self.client.tls_set()
        prefix = str(config.mqtt["topic_prefix"])
        junction_id = str(config.junction["id"])
        self.client.will_set(
            junction_status(prefix, junction_id),
            json.dumps({"online": False, "junctionId": junction_id}),
            qos=1,
            retain=True,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    def start(self) -> None:
        host = os.getenv("LIFELANE_MQTT_HOST", str(self.config.mqtt["broker"]))
        port = int(os.getenv("LIFELANE_MQTT_PORT", str(self.config.mqtt["port"])))
        self.client.connect_async(host, port, int(self.config.mqtt.get("keepalive_seconds", 30)))
        self.client.loop_start()
        self.state_callback("CONNECTING")

    def stop(self) -> None:
        try:
            self.publish_status({"online": False})
            self.client.disconnect()
        finally:
            self.client.loop_stop()

    def publish_status(self, data: dict) -> None:
        prefix = str(self.config.mqtt["topic_prefix"])
        junction_id = str(self.config.junction["id"])
        payload = {
            "schemaVersion": 1,
            "junctionId": junction_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **data,
        }
        self.client.publish(junction_status(prefix, junction_id), json.dumps(payload), qos=1, retain=True)

    def publish_event(self, event_type: str, reason: str) -> None:
        prefix = str(self.config.mqtt["topic_prefix"])
        junction_id = str(self.config.junction["id"])
        self.client.publish(
            junction_events(prefix, junction_id),
            json.dumps({
                "schemaVersion": 1,
                "junctionId": junction_id,
                "eventType": event_type,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }),
            qos=1,
        )

    def publish_request(self, ambulance_id: str, trip_id: str, status: str) -> None:
        prefix = str(self.config.mqtt["topic_prefix"])
        junction_id = str(self.config.junction["id"])
        self.client.publish(
            junction_request(prefix, junction_id),
            json.dumps({
                "schemaVersion": 1, "junctionId": junction_id,
                "ambulanceId": ambulance_id, "tripId": trip_id, "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }),
            qos=1,
        )

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code != 0:
            self.state_callback(f"ERROR {reason_code}")
            return
        prefix = str(self.config.mqtt["topic_prefix"])
        client.subscribe(ambulance_telemetry(prefix), qos=1)
        client.subscribe(ambulance_emergency(prefix), qos=1)
        client.subscribe(ambulance_cancel(prefix), qos=1)
        client.subscribe(ambulance_status(prefix, "+"), qos=1)
        self.publish_status({"online": True})
        self.state_callback("CONNECTED")

    def _on_disconnect(self, _client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
        self.state_callback("DISCONNECTED" if reason_code == 0 else "RECONNECTING")

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            if message.topic.endswith("/cancel"):
                data = json.loads(message.payload.decode("utf-8"))
                self._validate_lifecycle(data, message.topic)
                self.cancel_callback(str(data["tripId"]))
                return
            if message.topic.endswith("/emergency"):
                data = json.loads(message.payload.decode("utf-8"))
                self._validate_lifecycle(data, message.topic)
                if not bool(data["emergencyActive"]):
                    self.cancel_callback(str(data["tripId"]))
                return
            if message.topic.endswith("/status"):
                if self.status_callback:
                    data = json.loads(message.payload.decode("utf-8"))
                    ambulance_id = str(data.get("ambulanceId", ""))
                    online = bool(data.get("online", False))
                    self.status_callback(ambulance_id, online)
                return
            self.packet_callback(validate_telemetry_payload(message.payload))
        except (InvalidMessage, KeyError, ValueError, UnicodeError) as exc:
            self.error_callback(f"Rejected MQTT message on {message.topic}: {exc}")

    def _validate_lifecycle(self, data: dict, topic: str) -> None:
        required = {"schemaVersion", "sequenceNumber", "ambulanceId", "tripId", "emergencyActive", "timestamp"}
        if not required.issubset(data) or int(data["schemaVersion"]) != 1:
            raise ValueError("invalid emergency lifecycle schema")
        ambulance_id, trip_id = str(data["ambulanceId"]), str(data["tripId"])
        topic_parts = topic.split("/")
        if ambulance_id not in self.config.authorized_ids or len(topic_parts) < 4 or topic_parts[2] != ambulance_id:
            raise ValueError("unauthorized or mismatched ambulance ID")
        age = (datetime.now(timezone.utc) - parse_timestamp(data["timestamp"])).total_seconds()
        if age > float(self.config.detection["maximum_packet_age_seconds"]) or age < -2:
            raise ValueError("stale lifecycle message")
        key = (ambulance_id, trip_id)
        sequence = int(data["sequenceNumber"])
        if sequence <= self._lifecycle_sequences.get(key, -1):
            raise ValueError("duplicate lifecycle sequence number")
        self._lifecycle_sequences[key] = sequence
