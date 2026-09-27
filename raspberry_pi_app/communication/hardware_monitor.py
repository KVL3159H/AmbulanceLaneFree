"""Read-only hardware status/ACK monitor; never synthesizes a hardware acknowledgement."""
import hashlib
import hmac
import json
import os
import uuid
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from .request_validator import matching_green_ack
from .message_validator import validate_telemetry_payload
from ..core.models import parse_timestamp


class HardwareMonitor:
    def __init__(self, config, callback, connection_callback):
        self.config, self.callback = config, callback
        self.requests = {}
        self.request_arrivals = {}
        self.response_times = {}
        self.secrets = json.loads(os.getenv("EMERGENCY_WAY_DEVICE_SECRETS", "{}"))
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="windows-monitor-"+uuid.uuid4().hex[:8])
        if os.getenv("LIFELANE_MQTT_USERNAME"):
            self.client.username_pw_set(os.environ["LIFELANE_MQTT_USERNAME"],os.getenv("LIFELANE_MQTT_PASSWORD"))
        if os.getenv("LIFELANE_MQTT_TLS","false").lower()=="true": self.client.tls_set()
        self.prefix=f"{config.mqtt['topic_prefix']}/junction/{config.junction['id']}"
        def connect(c,_u,_f,reason,_p):
            connection_callback("CONNECTED" if reason==0 else "ERROR")
            if reason==0: c.subscribe([(self.prefix+"/status",1),(self.prefix+"/ack",1),(self.prefix+"/priority",1),(f"{config.mqtt['topic_prefix']}/ambulance/+/telemetry2",1)])
        self.client.on_connect=connect
        self.client.on_disconnect=lambda *_:connection_callback("DISCONNECTED")
        self.client.on_message=self._message

    def start(self):
        self.client.connect_async(os.getenv("LIFELANE_MQTT_HOST",self.config.mqtt["broker"]),int(os.getenv("LIFELANE_MQTT_PORT",self.config.mqtt["port"])))
        self.client.loop_start()

    def stop(self):
        self.client.disconnect(); self.client.loop_stop()

    def publish_simulation(self, topic, payload):
        if not self.client.is_connected():
            raise ValueError("MQTT disconnected; HIL request was not sent")
        result = self.client.publish(topic,payload,qos=1,retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ValueError("MQTT did not accept HIL message")

    def _message(self,_client,_userdata,message):
        try:
            envelope=json.loads(message.payload)
            if not isinstance(envelope,dict):
                return
            if message.topic.endswith("/status"):
                if envelope.get("controllerId")==self.config.junction["controller_id"] and envelope.get("mode")=="physical":
                    self.callback(envelope)
                return
            raw=envelope["payload"]; data=json.loads(raw); secret=self.secrets.get(data["ambulanceId"])
            if not secret or not hmac.compare_digest(hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest(),envelope["signature"]): return
            if data["ambulanceId"] not in self.config.authorized_ids: return
            if message.topic.endswith("/telemetry2"):
                packet=validate_telemetry_payload(raw)
                if packet.ambulance_id != message.topic.split("/")[-2] or packet.upcoming_junction_id != self.config.junction['id']: return
                self.callback({"messageType":"AUTHENTICATED_TELEMETRY","controllerId":self.config.junction['controller_id'],"packet":packet.to_dict(),"sourceMode":data.get("sourceMode","LIVE_PHONE")})
                return
            if data.get("junctionId")!=self.config.junction['id'] or data.get("controllerId")!=self.config.junction['controller_id']: return
            if message.topic.endswith("/priority"):
                self.requests[data["requestId"]]=data
                self.request_arrivals.setdefault(data["requestId"],time.monotonic())
            else:
                if data.get("mode")!="HARDWARE": return
                if not 0 <= (datetime.now(timezone.utc)-parse_timestamp(data["acknowledgementTimestamp"])).total_seconds() <= 5: return
                request=self.requests.get(data["requestId"])
                data["verifiedGrant"] = bool(request and data.get("mode")=="HARDWARE" and matching_green_ack(data,request,datetime.now(timezone.utc)))
                data["matchedRequest"]=request
                if data["requestId"] in self.request_arrivals:
                    self.response_times.setdefault(data["requestId"],time.monotonic()-self.request_arrivals[data["requestId"]])
                data["observedResponseSeconds"]=self.response_times.get(data["requestId"])
                self.callback(data)
        except (ValueError,TypeError,KeyError):
            return
