"""Version 2 authenticated requests. HMAC covers exact UTF-8 payload bytes."""
import hashlib
import hmac
import json
import math
from datetime import datetime, timezone

from ..core.models import parse_timestamp
from ..core.gps_engine import haversine_metres
from ..core.junction_registry import JunctionRegistry

REQUEST_FIELDS = set("schemaVersion messageType requestId tripId ambulanceId junctionId controllerId timestamp medicalPriority latitude longitude gpsAccuracy speed heading approachSide approachConfidence distanceToStopLine junctionEtaSeconds destinationHospitalId destinationHospitalName destinationLatitude destinationLongitude routeDistanceMetres routeEtaSeconds supportedJunctionCount".split())


class RequestValidator:
    def __init__(self, config, secrets, replay_file=None):
        self.config, self.secrets = config, secrets
        self.registry=JunctionRegistry([config])
        self.seen = {}
        self.replay_file = replay_file
        if replay_file is not None and replay_file.exists():
            self.seen = {key:parse_timestamp(stamp) for key,stamp in json.loads(replay_file.read_text(encoding="utf-8")).items()}

    def validate(self, envelope, now=None):
        now = now or datetime.now(timezone.utc)
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
            raise ValueError("signed envelope required")
        raw = envelope["payload"]
        if not isinstance(raw, str) or len(raw) > 16384:
            raise ValueError("invalid payload size")
        data = json.loads(raw)
        if not isinstance(data, dict) or not REQUEST_FIELDS.issubset(data):
            raise ValueError("missing required fields")
        identity = data["ambulanceId"]
        secret = self.secrets.get(identity)
        if identity not in self.config.authorized_ids or not secret:
            raise ValueError("unknown or unprovisioned ambulance")
        expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not isinstance(envelope["signature"], str) or not hmac.compare_digest(expected, envelope["signature"]):
            raise ValueError("authentication failed")
        if type(data["schemaVersion"]) is not int or data["schemaVersion"] != 2 or data["messageType"] != "PRIORITY_REQUEST":
            raise ValueError("unsupported protocol")
        self.registry.resolve(data["junctionId"],data["controllerId"])
        age = (now - parse_timestamp(data["timestamp"])).total_seconds()
        if not -2 <= age <= float(self.config.detection["maximum_packet_age_seconds"]):
            raise ValueError("expired request or stale GPS")
        for field in ("requestId", "tripId", "destinationHospitalId", "destinationHospitalName"):
            if not isinstance(data[field], str) or not 1 <= len(data[field]) <= 120:
                raise ValueError(f"invalid {field}")
        if data["approachSide"] not in {"NORTH", "EAST", "SOUTH", "WEST"}:
            raise ValueError("unsupported approach")
        if data["medicalPriority"] not in {"Critical", "Serious", "Stable"}:
            raise ValueError("unsupported medical priority")
        for field in ("latitude", "longitude", "gpsAccuracy", "speed", "heading", "approachConfidence", "distanceToStopLine", "junctionEtaSeconds", "destinationLatitude", "destinationLongitude", "routeDistanceMetres", "routeEtaSeconds", "supportedJunctionCount"):
            if type(data[field]) not in (int, float) or not math.isfinite(data[field]):
                raise ValueError(f"invalid {field}")
        if not -90 <= data["latitude"] <= 90 or not -180 <= data["longitude"] <= 180:
            raise ValueError("invalid coordinates")
        if not -90 <= data["destinationLatitude"] <= 90 or not -180 <= data["destinationLongitude"] <= 180:
            raise ValueError("invalid destination coordinates")
        if data["routeDistanceMetres"] < 0 or data["routeEtaSeconds"] < 0 or type(data["supportedJunctionCount"]) is not int or data["supportedJunctionCount"] < 1:
            raise ValueError("invalid route metadata")
        if not 0 <= data["gpsAccuracy"] <= self.config.detection["maximum_accuracy_metres"]:
            raise ValueError("poor GPS accuracy")
        if not 2 <= data["speed"] <= 70 or not 0 <= data["heading"] < 360 or not 80 <= data["approachConfidence"] <= 100:
            raise ValueError("unconfirmed approach")
        if data["distanceToStopLine"] < 0 or data["junctionEtaSeconds"] < 0:
            raise ValueError("request is past stop line or invalid ETA")
        distance = haversine_metres(data["latitude"], data["longitude"], self.config.junction["latitude"], self.config.junction["longitude"])
        if distance > self.config.detection.get("monitoring_distance_metres", 1000):
            raise ValueError("outside coverage")
        self.seen = {key: stamp for key, stamp in self.seen.items() if (now-stamp).total_seconds() < 86400}
        if data["requestId"] in self.seen:
            raise ValueError("duplicate request ID")
        self.seen[data["requestId"]] = now
        if self.replay_file is not None:
            self.replay_file.parent.mkdir(parents=True,exist_ok=True)
            temporary = self.replay_file.with_suffix(".tmp")
            temporary.write_text(json.dumps({key:stamp.isoformat() for key,stamp in self.seen.items()}),encoding="utf-8")
            temporary.replace(self.replay_file)
        return data


def matching_green_ack(ack, request, now, maximum_age=5):
    try:
        if ack["schemaVersion"] != 2 or ack["messageType"] != "PRIORITY_ACK":
            return False
        if any(ack[key] != request[key] for key in ("requestId", "tripId", "ambulanceId", "junctionId", "controllerId")):
            return False
        if not 0 <= (now-parse_timestamp(ack["acknowledgementTimestamp"])).total_seconds() <= maximum_age:
            return False
        side = request["approachSide"]
        lamps = ack["lampState"]
        return (ack["accepted"] is True and ack["controllerState"] == "PRIORITY_GREEN"
                and ack["grantedApproach"] == side and set(lamps) == {"NORTH", "EAST", "SOUTH", "WEST"}
                and all(value == ("GREEN" if key == side else "RED") for key, value in lamps.items()))
    except (KeyError, TypeError, ValueError):
        return False
