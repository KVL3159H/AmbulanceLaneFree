"""LifeLane Web Application Server.

Zero-dependency Python HTTP server with real-time Server-Sent Events (SSE)
streaming for the browser-based junction simulator and traffic preemption dashboard.

Integrates directly with the existing LifeLane coordinator, GPS engine, and
simulator infrastructure.  No Flask/FastAPI required — uses only the Python
standard library (http.server + threading + json).

Usage:
    python -m web_app.server            # Default: http://localhost:5000
    python -m web_app.server --port 8080
    python -m web_app.server --no-browser
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import queue
import socket
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root on sys.path so we can import raspberry_pi_app.*
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import hashlib
import hmac
import paho.mqtt.client as mqtt

from raspberry_pi_app.communication.hardware_bridge import HardwareBridge
from raspberry_pi_app.communication.local_broker import LocalBroker
from raspberry_pi_app.core.config import load_config
from raspberry_pi_app.core.coordinator import LifeLaneCoordinator
from raspberry_pi_app.core.models import (
    Approach,
    PatientPriority,
    TelemetryPacket,
)
from raspberry_pi_app.core.signal_states import PreemptionState, SignalColour
from raspberry_pi_app.simulator.ambulance_factory import create_simulated_ambulance
from raspberry_pi_app.simulator.gps_simulator import SimulatedAmbulance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lifelane.web")

# ---------------------------------------------------------------------------
# Globals shared between simulation loop and HTTP handler threads
# ---------------------------------------------------------------------------
_config = None
_coordinator: LifeLaneCoordinator | None = None
_simulations: list[SimulatedAmbulance] = []
_sim_elapsed: dict[str, float] = {}
_event_log: list[dict] = []
_sse_clients: list[queue.SimpleQueue] = []
_state_lock = threading.Lock()
_TICK_RATE = 0.10  # 10 Hz
_hardware_bridge: HardwareBridge | None = None
_local_broker: LocalBroker | None = None
_mqtt_client: mqtt.Client | None = None
_mqtt_connected: bool = False


# ---------------------------------------------------------------------------
# SSE broadcasting
# ---------------------------------------------------------------------------

def _broadcast(data: dict) -> None:
    payload = "data: " + json.dumps(data) + "\n\n"
    dead = []
    for q in list(_sse_clients):
        try:
            q.put_nowait(payload)
        except Exception:
            dead.append(q)
    for q in dead:
        try:
            _sse_clients.remove(q)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Event callback wired into the coordinator
# ---------------------------------------------------------------------------

def _on_event(event_type: str, message: str) -> None:
    entry = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "type": event_type,
        "msg": message,
    }
    with _state_lock:
        _event_log.append(entry)
        if len(_event_log) > 200:
            _event_log.pop(0)
    _broadcast({"kind": "event", "payload": entry})


# ---------------------------------------------------------------------------
# State snapshot builder
# ---------------------------------------------------------------------------

def _signal_colour_to_str(colour: SignalColour) -> str:
    return colour.value.lower()


def _build_state() -> dict:
    ctrl = _coordinator.controller
    signals = {side.value: _signal_colour_to_str(colour) for side, colour in ctrl.signals.items()}
    ordered = _coordinator.priority.ordered()
    queue_items = []
    for req in ordered:
        queue_items.append({
            "trip_id": req.trip_id,
            "ambulance_id": req.ambulance_id,
            "approach": req.approach.value,
            "priority": req.priority.value,
            "distance_m": round(req.distance_metres, 1),
            "eta_s": round(req.eta_seconds, 1) if req.eta_seconds is not None else None,
            "status": req.status.value,
            "waiting_s": round(req.waiting_seconds, 1),
        })

    ambulances = []
    seen_ids = set()
    for sim in list(_simulations):
        if sim.finished:
            continue
        ambulances.append({
            "id": sim.ambulance_id,
            "trip_id": sim.trip_id,
            "side": sim.starting_side.value,
            "dist_m": round(sim.signed_distance_metres, 1),
            "speed_mps": sim.speed_mps,
            "priority": sim.priority.value,
            "active": sim.active,
        })
        seen_ids.add(sim.ambulance_id)

    now_utc = datetime.now(timezone.utc)
    for trip_id, assessment in list(_coordinator.latest.items()):
        if assessment.packet.ambulance_id in seen_ids:
            continue
        age = (now_utc - assessment.packet.timestamp).total_seconds()
        if age > 60:
            continue
        side_str = assessment.approach.value if assessment.approach else (assessment.packet.approach_side or "EAST").upper()
        dist = assessment.distance_metres if assessment.distance_metres is not None else (assessment.route_distance_metres or 0.0)
        ambulances.append({
            "id": assessment.packet.ambulance_id,
            "trip_id": trip_id,
            "side": side_str,
            "dist_m": round(dist, 1),
            "speed_mps": assessment.filtered_speed_mps,
            "priority": assessment.packet.patient_priority.value,
            "active": not assessment.cleared,
        })
        seen_ids.add(assessment.packet.ambulance_id)

    target_trip = ctrl.target_trip_id
    target_info: dict[str, Any] = {}
    if target_trip and target_trip in _coordinator.latest:
        a = _coordinator.latest[target_trip]
        target_info = {
            "ambulance_id": a.packet.ambulance_id,
            "distance_m": round(a.distance_metres or 0, 1),
            "eta_s": round(a.eta_seconds or 0, 1),
            "speed_mps": round(a.filtered_speed_mps, 2),
            "approach": a.approach.value if a.approach else None,
            "approaching": a.approaching,
        }

    remaining = _remaining_time()

    return {
        "kind": "state",
        "signals": signals,
        "preemption_state": ctrl.state.value,
        "normal_phase": ctrl.normal_phase.value if ctrl.state is PreemptionState.NORMAL else None,
        "running": ctrl.running,
        "target_trip": target_trip,
        "target": target_info,
        "queue": queue_items,
        "ambulances": ambulances,
        "remaining_s": remaining,
        "events": list(_event_log[-20:]),
        "connected_ambulance_ids": [a["id"] for a in ambulances],
        "sse_clients": len(_sse_clients),
    }


def _mqtt_status() -> dict:
    """Return a snapshot of MQTT broker connectivity and connected ambulance IDs."""
    now_utc = datetime.now(timezone.utc)
    with _state_lock:
        active_ambs = []
        seen = set()
        for trip_id, assessment in list(_coordinator.latest.items()):
            if (now_utc - assessment.packet.timestamp).total_seconds() <= 60:
                side_str = assessment.approach.value if assessment.approach else (assessment.packet.approach_side or "EAST").upper()
                active_ambs.append({
                    "id": assessment.packet.ambulance_id,
                    "trip_id": trip_id,
                    "side": side_str,
                    "priority": assessment.packet.patient_priority.value,
                })
                seen.add(assessment.packet.ambulance_id)
        for sim in _simulations:
            if not sim.finished and sim.ambulance_id not in seen:
                active_ambs.append({
                    "id": sim.ambulance_id,
                    "trip_id": sim.trip_id,
                    "side": sim.starting_side.value,
                    "priority": sim.priority.value,
                })
    return {
        "broker_connected": _mqtt_connected,
        "ambulance_count": len(active_ambs),
        "ambulances": active_ambs,
        "sse_clients": len(_sse_clients),
    }


def _remaining_time() -> float | None:
    from raspberry_pi_app.core.signal_states import NormalPhase, PreemptionState as PS
    ctrl = _coordinator.controller
    timing = _config.timing
    if not ctrl.running:
        return None
    if ctrl.state is PS.NORMAL:
        duration_map = {
            NormalPhase.NS_GREEN: timing["normal_green_seconds"],
            NormalPhase.NS_YELLOW: timing["yellow_seconds"],
            NormalPhase.ALL_RED_BEFORE_EW: timing["all_red_seconds"],
            NormalPhase.EW_GREEN: timing["normal_green_seconds"],
            NormalPhase.EW_YELLOW: timing["yellow_seconds"],
            NormalPhase.ALL_RED_BEFORE_NS: timing["all_red_seconds"],
        }
        duration = duration_map.get(ctrl.normal_phase, 0.0)
    elif ctrl.state in {PS.CLEAR_CURRENT_GREEN, PS.RECOVERY_YELLOW}:
        duration = timing["yellow_seconds"]
    elif ctrl.state in {PS.ALL_RED_CLEARANCE, PS.RECOVERY_ALL_RED}:
        duration = timing["all_red_seconds"]
    elif ctrl.state is PS.PREEMPTION_PENDING:
        duration = ctrl._pending_minimum_green
    elif ctrl.state in {PS.AMBULANCE_GREEN, PS.PASSAGE_MONITORING}:
        duration = timing["maximum_ambulance_green_seconds"]
    else:
        return None
    return round(max(0.0, float(duration) - ctrl.elapsed), 1)


# ---------------------------------------------------------------------------
# MQTT Integration (Listens to real mobile app telemetry & sends priority ACK)
# ---------------------------------------------------------------------------

def _parse_telemetry(raw: bytes | str) -> TelemetryPacket | None:
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        if "payload" in data and "signature" in data and isinstance(data["payload"], str):
            data = json.loads(data["payload"])
        return TelemetryPacket.from_dict(data)
    except Exception as exc:
        logger.debug("Failed to parse telemetry packet: %s", exc)
        return None


def _handle_mqtt_priority_request(client: mqtt.Client, topic: str, raw_payload: bytes) -> None:
    try:
        env = json.loads(raw_payload.decode("utf-8"))
        if "payload" in env and "signature" in env and isinstance(env["payload"], str):
            req_data = json.loads(env["payload"])
        else:
            req_data = env

        amb_id = str(req_data.get("ambulanceId", ""))
        trip_id = str(req_data.get("tripId", ""))
        req_id = str(req_data.get("requestId", ""))
        approach_str = str(req_data.get("approach", req_data.get("direction", "EAST"))).upper()
        prio_str = str(req_data.get("medicalPriority", "RED")).upper()
        if prio_str in {"CRITICAL", "RED"}:
            prio = PatientPriority.RED
        elif prio_str in {"SERIOUS", "YELLOW"}:
            prio = PatientPriority.YELLOW
        else:
            prio = PatientPriority.GREEN

        try:
            appr = Approach(approach_str)
        except ValueError:
            appr = Approach.EAST

        dist = float(req_data.get("distanceToStopLine", 200.0))
        speed_val = max(float(req_data.get("speed", 10.0)), 1.0)
        eta = float(req_data.get("junctionEtaSeconds", dist / speed_val))

        with _state_lock:
            result = _coordinator.priority.request(
                trip_id=trip_id,
                ambulance_id=amb_id,
                approach=appr,
                distance_metres=dist,
                priority=prio,
                eta_seconds=eta,
                now_utc=datetime.now(timezone.utc),
            )

        _on_event("PRIORITY_REQUEST", f"{amb_id} requested priority on {appr.value} ({result.status.value})")
        _broadcast(_build_state())

        prefix = str(_config.mqtt.get("topic_prefix", "lifelane"))
        junc_id = str(_config.junction.get("id", "junc-001"))
        ack_topic = f"{prefix}/junction/{junc_id}/ack"
        ack_payload = {
            "schemaVersion": 2,
            "messageType": "PRIORITY_ACK",
            "requestId": req_id,
            "tripId": trip_id,
            "ambulanceId": amb_id,
            "junctionId": junc_id,
            "status": "GRANTED" if result.status.value in {"GRANTED", "ACTIVE", "WAITING", "EXTENDED"} else result.status.value,
            "grantedApproach": appr.value,
            "controllerState": _coordinator.controller.state.value,
            "acknowledgementTimestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        raw_ack = json.dumps(ack_payload)
        secrets = getattr(_config, "secrets", {})
        secret = secrets.get(amb_id, os.getenv("DEVICE_SECRET", "dev-device-secret-key-32chars-min!!"))
        sig = hmac.new(secret.encode("utf-8"), raw_ack.encode("utf-8"), hashlib.sha256).hexdigest()
        envelope = {"payload": raw_ack, "signature": sig}
        client.publish(ack_topic, json.dumps(envelope), qos=1)
        logger.info("Published priority ACK for %s on %s", amb_id, ack_topic)
    except Exception as exc:
        logger.warning("Error processing priority request: %s", exc)


def _start_mqtt(host: str = "127.0.0.1", port: int = 1883) -> None:
    global _local_broker, _mqtt_client, _mqtt_connected

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    res = sock.connect_ex((host, port))
    sock.close()
    if res != 0:
        logger.info("No active MQTT broker detected on %s:%d. Starting embedded broker...", host, port)
        try:
            _local_broker = LocalBroker(port)
            _local_broker.start()
            logger.info("Embedded MQTT broker started on port %d", port)
        except Exception as e:
            logger.warning("Could not start embedded MQTT broker: %s", e)

    try:
        from raspberry_pi_app.communication.discovery_beacon import start_discovery_beacon
        start_discovery_beacon(mqtt_port=port, web_port=5000)
    except Exception as exc:
        logger.debug("Could not start discovery beacon: %s", exc)

    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="lifelane-web-dashboard",
            clean_session=True,
        )

        def on_connect(c, _userdata, _flags, reason_code, _properties=None):
            global _mqtt_connected
            if reason_code == 0:
                _mqtt_connected = True
                logger.info("Web dashboard connected to MQTT broker on %s:%d", host, port)
                prefix = str(_config.mqtt.get("topic_prefix", "lifelane"))
                c.subscribe(f"{prefix}/ambulance/+/telemetry", qos=1)
                c.subscribe(f"{prefix}/ambulance/+/telemetry2", qos=1)
                c.subscribe(f"{prefix}/ambulance/+/emergency", qos=1)
                c.subscribe(f"{prefix}/ambulance/+/cancel", qos=1)
                c.subscribe(f"{prefix}/junction/+/priority", qos=1)
                c.subscribe(f"{prefix}/junction/+/control", qos=1)
                _on_event("MQTT_CONNECTED", f"Connected to broker on {host}:{port}")
            else:
                _mqtt_connected = False
                logger.warning("MQTT connection failed with code: %s", reason_code)

        def on_disconnect(c, _userdata, _disconnect_flags, reason_code, _properties=None):
            global _mqtt_connected
            _mqtt_connected = False
            logger.info("MQTT disconnected (code %s)", reason_code)

        def on_message(c, _userdata, message):
            try:
                topic = message.topic
                raw_payload = message.payload
                now_utc = datetime.now(timezone.utc)

                if topic.endswith("/telemetry") or topic.endswith("/telemetry2"):
                    packet = _parse_telemetry(raw_payload)
                    if packet:
                        with _state_lock:
                            assessment = _coordinator.process_packet(packet, now_utc)
                        side_str = assessment.approach.value if assessment.approach else (packet.approach_side or "")
                        dist_val = packet.distance_to_stop_line if packet.distance_to_stop_line is not None else 0.0
                        _on_event("TELEMETRY", f"{packet.ambulance_id} ({side_str or 'approaching'}) dist={dist_val:.0f}m speed={packet.speed_mps:.1f}m/s")
                        _broadcast(_build_state())

                elif topic.endswith("/emergency"):
                    data = json.loads(raw_payload.decode("utf-8"))
                    trip_id = str(data.get("tripId", ""))
                    if not bool(data.get("emergencyActive", True)):
                        with _state_lock:
                            _coordinator.cancel(trip_id, "Emergency finished")
                        _on_event("EMERGENCY_ENDED", f"Trip {trip_id} completed")
                        _broadcast(_build_state())

                elif topic.endswith("/cancel"):
                    data = json.loads(raw_payload.decode("utf-8"))
                    trip_id = str(data.get("tripId", ""))
                    with _state_lock:
                        _coordinator.cancel(trip_id, "Cancelled by vehicle")
                    _on_event("TRIP_CANCELLED", f"Trip {trip_id} cancelled")
                    _broadcast(_build_state())

                elif topic.endswith("/priority"):
                    _handle_mqtt_priority_request(c, topic, raw_payload)

                elif topic.endswith("/control"):
                    data = json.loads(raw_payload.decode("utf-8"))
                    if str(data.get("messageType")) == "PRIORITY_CANCEL":
                        trip_id = str(data.get("tripId", ""))
                        with _state_lock:
                            _coordinator.cancel(trip_id, "Priority cancelled by client")
                        _on_event("PRIORITY_CANCEL", f"Trip {trip_id} preemption cancelled")
                        _broadcast(_build_state())

            except Exception as exc:
                logger.debug("MQTT message processing exception on %s: %s", message.topic, exc)

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        client.connect_async(host, port, keepalive=30)
        client.loop_start()
        _mqtt_client = client
    except Exception as err:
        logger.warning("Could not initialize MQTT client: %s", err)


def _stop_mqtt() -> None:
    global _mqtt_client, _local_broker, _mqtt_connected
    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except Exception:
            pass
        _mqtt_client = None
    _mqtt_connected = False
    if _local_broker:
        try:
            _local_broker.stop()
        except Exception:
            pass
        _local_broker = None
    try:
        from raspberry_pi_app.communication.discovery_beacon import stop_discovery_beacon
        stop_discovery_beacon()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------

def _simulation_loop() -> None:
    last = time.monotonic()
    while True:
        now_mono = time.monotonic()
        dt = min(now_mono - last, 0.5)  # cap at 0.5s to avoid huge jumps
        last = now_mono
        now_utc = datetime.now(timezone.utc)

        with _state_lock:
            for sim in list(_simulations):
                _sim_elapsed[sim.trip_id] = _sim_elapsed.get(sim.trip_id, 0.0) + dt
                if _sim_elapsed[sim.trip_id] >= sim.packet_delay_seconds:
                    _sim_elapsed[sim.trip_id] = 0.0
                    pkt = sim.next_packet(now_utc)
                    if pkt:
                        _coordinator.process_packet(pkt, now_utc)
                if sim.finished:
                    _simulations.remove(sim)
                    _sim_elapsed.pop(sim.trip_id, None)

            _coordinator.tick(dt, now_utc)
            if _hardware_bridge:
                _hardware_bridge.send_signals(_coordinator.controller.signals, _coordinator.controller.state)

        _broadcast(_build_state())
        sleep_time = max(0.0, _TICK_RATE - (time.monotonic() - now_mono))
        time.sleep(sleep_time)


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class LifeLaneHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt: str, *args: Any) -> None:
        if args and str(args[1]) not in ("200", "304"):
            logger.debug("HTTP %s %s %s", *args)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._serve_index()
        elif path == "/api/stream":
            self._serve_sse()
        elif path == "/api/status":
            self._json(200, _build_state())
        elif path == "/api/mqtt/status":
            self._json(200, _mqtt_status())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        body = self._read_body()
        if path == "/api/simulate/spawn":
            self._handle_spawn(body)
        elif path == "/api/simulate/clear":
            self._handle_clear()
        elif path == "/api/signal/cycle":
            self._handle_cycle(body)
        elif path == "/api/signal/override":
            self._handle_override(body)
        elif path == "/api/signal/reset":
            self._handle_reset()
        else:
            self._json(404, {"error": "not found"})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _handle_spawn(self, body: dict) -> None:
        side_str = str(body.get("side", "NORTH")).upper()
        try:
            side = Approach(side_str)
        except ValueError:
            self._json(400, {"error": f"Invalid side: {side_str}"}); return
        priority_str = str(body.get("priority", "RED")).upper()
        try:
            priority = PatientPriority(priority_str)
        except ValueError:
            priority = PatientPriority.RED
        speed = float(body.get("speed_mps", _config.simulation["ambulance_speed_mps"]))
        with _state_lock:
            sim = create_simulated_ambulance(_config, side, priority=priority, speed_mps=speed)
            _simulations.append(sim)
            _sim_elapsed[sim.trip_id] = sim.packet_delay_seconds
        _on_event("SIMULATION_STARTED", f"{sim.ambulance_id} deployed from {side.value} at {speed:.1f} m/s")
        self._json(200, {"ok": True, "trip_id": sim.trip_id, "ambulance_id": sim.ambulance_id})

    def _handle_clear(self) -> None:
        with _state_lock:
            for sim in list(_simulations):
                sim.active = False
                _coordinator.cancel(sim.trip_id, "Cleared by operator")
            _simulations.clear()
            _sim_elapsed.clear()
        _on_event("SIMULATION_CLEARED", "All simulated ambulances removed")
        self._json(200, {"ok": True})

    def _handle_cycle(self, body: dict) -> None:
        action = str(body.get("action", "")).lower()
        if action == "start":
            _coordinator.controller.start()
            self._json(200, {"ok": True})
        elif action == "pause":
            _coordinator.controller.pause()
            self._json(200, {"ok": True})
        else:
            self._json(400, {"error": "action must be start or pause"})

    def _handle_override(self, body: dict) -> None:
        action = str(body.get("action", "")).upper()
        if action == "ALL_RED":
            ctrl = _coordinator.controller
            ctrl.running = False
            ctrl.signals = {side: SignalColour.RED for side in Approach}
            _on_event("MANUAL_OVERRIDE", "All-red safe halt by operator")
            self._json(200, {"ok": True})
        else:
            self._json(400, {"error": "Unknown override action"})

    def _handle_reset(self) -> None:
        with _state_lock:
            for sim in list(_simulations):
                sim.active = False
            _simulations.clear()
            _sim_elapsed.clear()
            _coordinator.reset()
        _on_event("CONTROLLED_RESET", "Junction reset to all-red safe state")
        self._json(200, {"ok": True})

    def _serve_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors_headers()
        self.end_headers()
        q: queue.SimpleQueue = queue.SimpleQueue()
        _sse_clients.append(q)
        try:
            initial = "data: " + json.dumps(_build_state()) + "\n\n"
            self.wfile.write(initial.encode())
            self.wfile.flush()
        except Exception:
            try:
                _sse_clients.remove(q)
            except ValueError:
                pass
            return
        try:
            while True:
                try:
                    payload = q.get(timeout=25)
                    self.wfile.write(payload.encode())
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                _sse_clients.remove(q)
            except ValueError:
                pass

    def _serve_index(self) -> None:
        html_path = Path(__file__).parent / "static" / "index.html"
        if not html_path.exists():
            self._json(500, {"error": "index.html not found"}); return
        content = html_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def main() -> None:
    global _config, _coordinator

    parser = argparse.ArgumentParser(description="LifeLane Web Application Server")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--config", type=Path,
                        default=_PROJECT_ROOT / "config" / "junction.yaml")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    _config = load_config(args.config)
    _coordinator = LifeLaneCoordinator(_config, repository=None, event_callback=_on_event)
    _coordinator.controller.running = True
    _on_event("SAFE_INITIALIZATION", "Web server started - junction in all-red safe state")

    global _hardware_bridge
    _hardware_bridge = HardwareBridge()
    _hardware_bridge.start()

    sim_thread = threading.Thread(target=_simulation_loop, daemon=True)
    sim_thread.start()

    _start_mqtt(
        host=os.getenv("LIFELANE_MQTT_HOST", str(_config.mqtt.get("broker", "127.0.0.1"))),
        port=int(os.getenv("LIFELANE_MQTT_PORT", str(_config.mqtt.get("port", 1883)))),
    )

    server = HTTPServer(("0.0.0.0", args.port), LifeLaneHandler)
    lan_ip = get_local_ip()
    url = f"http://localhost:{args.port}"
    lan_url = f"http://{lan_ip}:{args.port}"

    logger.info("=" * 64)
    logger.info("  LifeLane Web Dashboard")
    logger.info("  Local : %s", url)
    logger.info("  LAN   : %s  (open on mobile/phone)", lan_url)
    logger.info("=" * 64)

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down LifeLane web server.")
    finally:
        _stop_mqtt()
        if _hardware_bridge:
            _hardware_bridge.stop()
        server.shutdown()


if __name__ == "__main__":
    main()
