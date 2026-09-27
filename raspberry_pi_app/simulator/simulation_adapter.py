"""Authenticated HIL producer. Signal decisions remain exclusively on the Pi."""
import hashlib
import hmac
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from ..core.gps_engine import GPSEngine
from .simulated_paths import metres_to_coordinates, offset_for_side


class SimulationAdapter:
    def __init__(self, config, secrets, publish):
        self.config, self.secrets, self.publish = config, secrets, publish
        self.gps = GPSEngine(config)
        self.request_ids = {}
        self.sent = set()
        self.identities = {}
        self.reject_next = False

    def envelope(self, identity, data):
        secret = self.secrets.get(identity)
        if identity not in self.config.authorized_ids or not secret:
            raise ValueError("HIL ambulance must be allowlisted and provisioned with a device secret")
        raw = json.dumps(data, separators=(",", ":"), allow_nan=False)
        return json.dumps({"payload":raw,"signature":hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()})

    def process(self, packet):
        request_id = self.request_ids.setdefault(packet.trip_id, str(uuid.uuid4()))
        self.identities[packet.trip_id] = packet.ambulance_id
        packet = replace(packet, request_id=request_id,upcoming_junction_id=self.config.junction['id'],supported_junction_count=1)
        assessment = self.gps.assess(packet)
        prefix = self.config.mqtt['topic_prefix']
        self.publish(f"{prefix}/ambulance/{packet.ambulance_id}/telemetry2", self.envelope(packet.ambulance_id, {**packet.to_dict(),"sourceMode":"SIMULATION"}))
        if not assessment.eligible or packet.trip_id in self.sent:
            return assessment
        from ..core.route_geometry import project_polyline,local_point
        path=self.config.raw['geometry']['paths'][assessment.approach.value]
        east,north=path[-1]
        latitude, longitude = metres_to_coordinates(self.config.junction['latitude'], self.config.junction['longitude'], north, east)
        projection=project_polyline(local_point(packet.latitude,packet.longitude,self.config.junction['latitude'],self.config.junction['longitude']),path)
        distance=max(0,projection.total-projection.progress)
        request = dict(schemaVersion=2,messageType="PRIORITY_REQUEST",requestId=request_id,
            tripId=packet.trip_id,ambulanceId=packet.ambulance_id,junctionId=self.config.junction['id'],
            controllerId=self.config.junction['controller_id'],timestamp=packet.timestamp.isoformat(),
            medicalPriority={"RED":"Critical","YELLOW":"Serious","GREEN":"Stable"}[packet.patient_priority.value],
            latitude=packet.latitude,longitude=packet.longitude,gpsAccuracy=packet.accuracy_metres,
            speed=packet.speed_mps,heading=packet.heading_degrees,travelHeading=packet.heading_degrees,approachSide=assessment.approach.value,
            approachConfidence=assessment.approach_confidence,distanceToStopLine=assessment.route_distance_metres,
            junctionEtaSeconds=assessment.eta_seconds,destinationHospitalId="SIM-EXIT",
            destinationHospitalName="Simulation route endpoint",destinationLatitude=latitude,destinationLongitude=longitude,
            routeDistanceMetres=distance,routeEtaSeconds=distance/max(packet.speed_mps,2),supportedJunctionCount=1,
            sourceMode="HARDWARE_IN_LOOP")
        if self.reject_next:
            request['approachConfidence']=0
            self.reject_next=False
        self.publish(f"{prefix}/junction/{self.config.junction['id']}/priority",self.envelope(packet.ambulance_id,request))
        self.sent.add(packet.trip_id)
        return assessment

    def cancel(self, trip_id):
        if trip_id not in self.sent:
            return
        identity = self.identities[trip_id]
        data = dict(schemaVersion=2,messageType="CANCEL",requestId=self.request_ids[trip_id],
                    tripId=trip_id,ambulanceId=identity,timestamp=datetime.now(timezone.utc).isoformat())
        self.publish(f"{self.config.mqtt['topic_prefix']}/junction/{self.config.junction['id']}/control",self.envelope(identity,data))
