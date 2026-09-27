"""Exercise actual TCP MQTT traffic through the bundled broker and desktop UI."""
import json
import socket
import threading
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt

from raspberry_pi_app.communication.local_broker import LocalBroker
from raspberry_pi_app.database.connection import connect_database
from raspberry_pi_app.database.repository import Repository
from raspberry_pi_app.ui.main_window import MainWindow


def test_mobile_telemetry_acknowledgement_and_cancel(config, qtbot, monkeypatch):
    for key in ("LIFELANE_MQTT_HOST", "LIFELANE_MQTT_PORT", "LIFELANE_MQTT_USERNAME", "LIFELANE_MQTT_TLS"):
        monkeypatch.delenv(key, raising=False)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    broker = LocalBroker(port)
    assert broker.start()
    # A second app must not stop or replace a broker already in use.
    assert not LocalBroker(port).start()
    config.mqtt.update(broker="127.0.0.1", port=port)
    window = MainWindow(config, Repository(connect_database(":memory:"), "JN-001"))
    qtbot.addWidget(window)
    phone = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test-phone")
    subscribed = threading.Event()
    messages = []
    phone.on_connect = lambda client, *_: client.subscribe("lifelane/junction/+/request", qos=1)
    phone.on_subscribe = lambda *_: subscribed.set()
    phone.on_message = lambda _c, _u, msg: messages.append(json.loads(msg.payload))
    try:
        phone.connect("127.0.0.1", port)
        phone.loop_start()
        qtbot.waitUntil(lambda: subscribed.is_set() and window.mqtt_state == "CONNECTED", timeout=5000)
        payload = {
            "schemaVersion": 1, "sequenceNumber": 1, "ambulanceId": "AMB-001",
            "tripId": "PHONE-TRIP", "requestId": "PHONE-REQUEST",
            "latitude": float(config.junction["latitude"]) + 0.0007,
            "longitude": float(config.junction["longitude"]), "accuracyMetres": 5,
            "speedMps": 10, "headingDegrees": 180, "patientPriority": "RED",
            "patientCondition": "CARDIAC", "destinationHospital": "Demo hospital",
            "emergencyActive": True, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        now = datetime.now(timezone.utc)
        for i in range(4):
            payload.update(sequenceNumber=i+1, latitude=float(config.junction["latitude"])+(110-10*i)/111320,
                           timestamp=(now-timedelta(seconds=3-i)).isoformat())
            phone.publish("lifelane/ambulance/AMB-001/telemetry", json.dumps(payload), qos=1)
        qtbot.waitUntil(lambda: window.coordinator.priority.get("PHONE-TRIP") is not None, timeout=5000)
        qtbot.waitUntil(lambda: any(m.get("requestId") == "PHONE-REQUEST" for m in messages), timeout=5000)
        payload.update(sequenceNumber=2, emergencyActive=False, timestamp=datetime.now(timezone.utc).isoformat())
        phone.publish("lifelane/ambulance/AMB-001/cancel", json.dumps(payload), qos=1)
        qtbot.waitUntil(lambda: any(m.get("status") == "CANCELLED" for m in messages), timeout=5000)
    finally:
        phone.disconnect()
        phone.loop_stop()
        window.close()
        broker.stop()
    # Shutdown releases the port, permitting the next desktop launch.
    replacement = LocalBroker(port)
    assert replacement.start()
    replacement.stop()


def test_broker_shutdown_closes_connected_clients():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    broker = LocalBroker(port)
    assert broker.start()
    phone = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="shutdown-phone")
    connected = threading.Event()
    phone.on_connect = lambda *_: connected.set()
    try:
        phone.connect("127.0.0.1", port)
        phone.loop_start()
        assert connected.wait(3)
        # Also close a TCP peer that never sent an MQTT CONNECT handshake.
        with socket.create_connection(("127.0.0.1", port)):
            broker.stop()
        assert not broker.thread.is_alive()
    finally:
        phone.disconnect()
        phone.loop_stop()
        broker.stop()
