"""Headless Pi laboratory runtime using the same FSM as the Qt simulator."""
import argparse
import json
import os
import queue
import time
from pathlib import Path
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from .communication.request_validator import RequestValidator
from .communication.message_validator import validate_telemetry_payload
from .core.config import load_config
from .core.models import parse_timestamp
from .core.coordinator import LifeLaneCoordinator
from .core.event_logger import EventLogger
from .core.gpio_driver import GPIODriver, GPIOZeroPins, MemoryPins
from .core.watchdog import Watchdog


class ControllerRuntime:
    def __init__(self, config, mode, secrets, backend=None):
        self.config, self.mode = config, mode
        pins = config.raw["gpio"]["pins"]
        if backend is None:
            backend = GPIOZeroPins([p for lamps in pins.values() for p in lamps.values()]) if mode in {"physical", "gpio-test"} else MemoryPins()
        self.output = GPIODriver(pins, backend, paired=config.timing.get("paired_movements", True))
        self.logger = EventLogger()
        self.coordinator = LifeLaneCoordinator(config, event_callback=self._event, automatic_requests=False)
        replay_file = config.source.parent.parent / "data" / "controller-request-replay.json" if mode == "physical" else None
        self.validator = RequestValidator(config, secrets, replay_file)
        self.requests = {}
        self.rejections = []
        self.watchdog = Watchdog(float(config.timing.get("watchdog_seconds", 2)), self.fail_safe)
        self.connected = False

    def _event(self, kind, reason):
        self.logger.record(sourceComponent="raspberry_pi", eventType=kind, result=reason,
                           junctionId=self.config.junction["id"])

    def fail_safe(self):
        self.output.fault = True
        self.output.all_red()
        self.coordinator.controller._enter_fail_safe("watchdog or runtime fault")

    def telemetry(self, raw, topic_identity):
        import hashlib, hmac
        envelope = json.loads(raw)
        payload = envelope["payload"]
        secret = self.validator.secrets.get(topic_identity)
        if not secret or not hmac.compare_digest(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest(), envelope["signature"]):
            raise ValueError("unauthenticated telemetry")
        packet = validate_telemetry_payload(payload)
        if packet.ambulance_id != topic_identity:
            raise ValueError("telemetry topic identity mismatch")
        return self.coordinator.process_packet(packet)

    def request(self, envelope):
        data = self.validator.validate(envelope)
        if data["tripId"] in self.coordinator.completed_trips:
            if self.coordinator.outcomes.get(data["tripId"]) != "CANCELLED":
                raise ValueError("junction already completed or timed out for this trip")
            if self.coordinator.controller.target_trip_id == data["tripId"]:
                raise ValueError("previous request still restoring normal operation")
        assessment = self.coordinator.latest.get(data["tripId"])
        if (assessment is None or not assessment.valid or not assessment.eligible or
            assessment.packet.ambulance_id != data["ambulanceId"] or
            assessment.packet.request_id != data["requestId"] or
            assessment.approach.value != data["approachSide"] or
            assessment.packet.timestamp != parse_timestamp(data["timestamp"]) or
            assessment.packet.latitude != data["latitude"] or assessment.packet.longitude != data["longitude"]):
            raise ValueError("request has no matching confirmed telemetry")
        self.coordinator.completed_trips.discard(data["tripId"])
        self.coordinator.outcomes.pop(data["tripId"],None)
        self.requests = {key:value for key,value in self.requests.items() if value["tripId"] != data["tripId"]}
        self.requests[data["requestId"]] = data
        self.coordinator.priority.add_or_update(assessment)
        self.coordinator._select_if_possible(datetime.now(timezone.utc))
        return data

    def reject(self, envelope, reason):
        # Only return identity-correlated rejection for an authenticated sender.
        import hashlib, hmac
        try:
            raw = envelope["payload"]; data = json.loads(raw)
            secret = self.validator.secrets.get(data["ambulanceId"])
            if not secret or not hmac.compare_digest(hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest(),envelope["signature"]):
                return
            self.rejections.append({**{k:data[k] for k in ("requestId","tripId","ambulanceId","junctionId","controllerId")},
                "schemaVersion":2,"messageType":"PRIORITY_ACK","accepted":False,"rejectionReason":reason,
                "queuePosition":0,"grantedApproach":"","controllerState":"REQUEST_REJECTED",
                "lampState":{s.value:c.value for s,c in self.output.applied.items()},
                "acknowledgementTimestamp":datetime.now(timezone.utc).isoformat(),
                "mode":"HARDWARE" if self.mode=="physical" else "SIMULATION"})
        except (ValueError,KeyError,TypeError):
            return

    def cancel(self, envelope):
        import hashlib, hmac
        raw = envelope["payload"]
        data = json.loads(raw)
        secret = self.validator.secrets.get(data["ambulanceId"])
        if not secret or not hmac.compare_digest(hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest(),envelope["signature"]):
            raise ValueError("unauthenticated cancellation")
        age = (datetime.now(timezone.utc)-parse_timestamp(data["timestamp"])).total_seconds()
        request = self.requests.get(data["requestId"])
        if not -2 <= age <= 5 or request is None or any(request[k] != data[k] for k in ("tripId","ambulanceId")):
            raise ValueError("stale or unmatched cancellation")
        self.coordinator.cancel(data["tripId"], "Authenticated cancellation")

    def tick(self, delta):
        self.coordinator.tick(delta)
        self.output.apply(self.coordinator.controller.signals)
        self.watchdog.feed()
        return self.acknowledgements()

    def acknowledgements(self):
        result = self.rejections
        self.rejections = []
        controller = self.coordinator.controller
        ordered = self.coordinator.priority.ordered()
        for data in self.requests.values():
            request = self.coordinator.priority.get(data["tripId"])
            state = controller.state.value
            active = controller.target_trip_id == data["tripId"]
            outcome = self.coordinator.outcomes.get(data["tripId"])
            if active and state in {"AMBULANCE_GREEN", "PASSAGE_MONITORING"}:
                state = "PRIORITY_GREEN"
            elif not active:
                state = "COMPLETED" if outcome == "JUNCTION_CLEARED" else (outcome or "CONTROLLER_VALIDATED")
            if active and outcome == "JUNCTION_CLEARED":
                state = "NORMAL_RESTORING"
            result.append({
                **{k:data[k] for k in ("requestId","tripId","ambulanceId","junctionId","controllerId")},
                "schemaVersion":2, "messageType":"PRIORITY_ACK", "accepted":outcome not in {"CANCELLED", "REQUEST_REJECTED"},
                "rejectionReason":"", "queuePosition":ordered.index(request)+1 if request in ordered else 0,
                "grantedApproach":data["approachSide"] if active else "", "controllerState":state,
                "junctionState":self.coordinator.junction_state(data["tripId"]).value,
                "lampState":{s.value:c.value for s,c in self.output.applied.items()},
                "acknowledgementTimestamp":datetime.now(timezone.utc).isoformat(),
                "mode":"HARDWARE" if self.mode == "physical" else "SIMULATION",
            })
        return result


def main():
    parser = argparse.ArgumentParser(description="Emergency Way laboratory controller")
    parser.add_argument("--mode", choices=["physical", "simulation", "gpio-test"], default="simulation")
    parser.add_argument("--config")
    parser.add_argument("--ticks", type=int, default=0, help="bounded initialization test; 0 runs continuously")
    args = parser.parse_args()
    config = load_config(args.config)
    secrets = json.loads(os.getenv("EMERGENCY_WAY_DEVICE_SECRETS", "{}"))
    if args.mode == "physical" and not (secrets and os.getenv("LIFELANE_MQTT_USERNAME")):
        raise SystemExit("Physical mode requires provisioned device secrets and MQTT credentials")
    runtime = ControllerRuntime(config, args.mode, secrets)
    inbox = queue.Queue(maxsize=1000)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config.junction["controller_id"])
    if os.getenv("LIFELANE_MQTT_USERNAME"):
        client.username_pw_set(os.environ["LIFELANE_MQTT_USERNAME"], os.getenv("LIFELANE_MQTT_PASSWORD"))
    if os.getenv("LIFELANE_MQTT_TLS", "false").lower() == "true":
        client.tls_set()
    prefix = f"{config.mqtt['topic_prefix']}/junction/{config.junction['id']}"
    client.will_set(prefix+"/status", json.dumps({"online":False,"controllerId":config.junction["controller_id"]}), qos=1, retain=True)
    def connected(c, _userdata, _flags, reason, _properties):
        runtime.connected = reason == 0
        if runtime.connected:
            c.subscribe([(f"{config.mqtt['topic_prefix']}/ambulance/+/telemetry2",1),(prefix+"/priority",1),(prefix+"/control",1)])
    def message(_c, _u, msg):
        try: inbox.put_nowait((msg.topic, bytes(msg.payload)))
        except queue.Full: runtime.fail_safe()
    client.on_connect = connected
    client.on_message = message
    client.on_disconnect = lambda *_: setattr(runtime, "connected", False)
    client.connect_async(os.getenv("LIFELANE_MQTT_HOST", config.mqtt["broker"]), int(config.mqtt["port"]))
    client.loop_start()
    runtime.watchdog.start()
    last = time.monotonic(); ticks = 0
    initialized = args.mode != "physical"
    try:
        while args.ticks == 0 or ticks < args.ticks:
            now = time.monotonic(); delta = now-last; last = now
            # Drain a bounded batch to guarantee watchdog and phase progress.
            for _ in range(100):
                try: topic, raw = inbox.get_nowait()
                except queue.Empty: break
                try:
                    if topic.endswith("/telemetry2"):
                        runtime.telemetry(raw, topic.split("/")[-2])
                    elif topic.endswith("/control"):
                        runtime.cancel(json.loads(raw))
                    else:
                        runtime.request(json.loads(raw))
                except (ValueError, TypeError, KeyError) as exc:
                    runtime._event("REQUEST_REJECTED", str(exc))
                    if topic.endswith("/priority"):
                        try:
                            runtime.reject(json.loads(raw), str(exc))
                        except (ValueError, TypeError):
                            pass
            if runtime.connected:
                initialized = True
            if runtime.connected or args.mode != "physical":
                for ack in runtime.tick(delta):
                    import hashlib, hmac
                    raw = json.dumps(ack)
                    secret = secrets[ack["ambulanceId"]]
                    envelope = {"payload":raw,"signature":hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()}
                    client.publish(prefix+"/ack", json.dumps(envelope), qos=1)
            else:
                # On startup remain all-red until broker initialization succeeds.
                # After a disconnect continue the bounded safe recovery cycle.
                if initialized:
                    trip = runtime.coordinator.controller.target_trip_id
                    if trip and trip not in runtime.coordinator.completed_trips:
                        runtime.coordinator.cancel(trip, "MQTT disconnected")
                    runtime.tick(delta)
                else:
                    runtime.output.all_red()
                    runtime.watchdog.feed()
            if ticks % 20 == 0:
                client.publish(prefix+"/status", json.dumps({"online":True,"controllerId":config.junction["controller_id"],"mode":args.mode,"controllerState":runtime.coordinator.controller.state.value,"lampState":{s.value:c.value for s,c in runtime.output.applied.items()},"timestamp":datetime.now(timezone.utc).isoformat()}),qos=1,retain=True)
            ticks += 1
            time.sleep(0.05)
    except Exception as exc:
        runtime._event("CONTROLLER_FAULT", str(exc))
        fault = {"online":False,"controllerId":config.junction["controller_id"],
                 "mode":args.mode,"controllerState":"FAIL_SAFE","failureReason":str(exc),
                 "lampStateVerified":False,"timestamp":datetime.now(timezone.utc).isoformat()}
        if client.is_connected():
            client.publish(prefix+"/status",json.dumps(fault),qos=1,retain=True).wait_for_publish(timeout=2)
        raise
    finally:
        runtime.watchdog.close()
        runtime.output.all_red()
        client.disconnect(); client.loop_stop()


if __name__ == "__main__":
    main()
