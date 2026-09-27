import hashlib
import hmac
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from raspberry_pi_app.communication.request_validator import RequestValidator, matching_green_ack
from raspberry_pi_app.core.gpio_driver import GPIODriver, MemoryPins
from raspberry_pi_app.core.gps_engine import GPSEngine, initial_bearing
from raspberry_pi_app.core.models import Approach
from raspberry_pi_app.core.route_geometry import project_polyline, inside_polygon
from raspberry_pi_app.core.signal_states import SignalColour
from raspberry_pi_app.core.watchdog import Watchdog
from raspberry_pi_app.simulator.traffic_engine import TrafficEngine


def signed(data, secret="laboratory-test-key"):
    raw = json.dumps(data)
    return {"payload":raw,"signature":hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()}


def request(config):
    return dict(schemaVersion=2,messageType="PRIORITY_REQUEST",requestId="REQ-1",tripId="TRIP-1",
        ambulanceId="AMB-001",junctionId=config.junction["id"],controllerId=config.junction["controller_id"],
        timestamp=datetime.now(timezone.utc).isoformat(),medicalPriority="Critical",latitude=config.junction["latitude"]+.001,
        longitude=config.junction["longitude"],gpsAccuracy=5,speed=10,heading=180,approachSide="NORTH",
        approachConfidence=95,distanceToStopLine=91,junctionEtaSeconds=9.1,destinationHospitalId="H-1",
        destinationHospitalName="Laboratory destination",destinationLatitude=9.44,destinationLongitude=77.55,
        routeDistanceMetres=1000,routeEtaSeconds=100,supportedJunctionCount=1)


def test_route_distance_follows_bend_and_signed_stop():
    projection = project_polyline((10,5),[(0,0),(10,0),(10,20)])
    assert projection.progress == 15
    assert projection.lateral == 0
    assert 12-projection.progress == -3
    assert inside_polygon((1,1),[(0,0),(2,0),(2,2),(0,2)])
    assert not inside_polygon((3,1),[(0,0),(2,0),(2,2),(0,2)])


@pytest.mark.parametrize("side,heading", [(Approach.NORTH,180),(Approach.EAST,270),(Approach.SOUTH,0),(Approach.WEST,90)])
def test_repeated_noisy_approach_is_stable(config,packet_factory,side,heading):
    engine=GPSEngine(config); now=datetime.now(timezone.utc)
    for i in range(8):
        stamp=now+timedelta(seconds=i)
        packet=packet_factory(side,distance=260-i*12+(i%2)*2,sequence=i+1,timestamp=stamp,heading=heading)
        assessment=engine.assess(packet,stamp)
        assert assessment.valid
    assert assessment.eligible and assessment.approach==side
    assert assessment.approach_confidence >= 80


@pytest.mark.parametrize("changes", [dict(speed_mps=100),dict(ambulance_id="AMB-UNREGISTERED"),dict(accuracy_metres=31)])
def test_invalid_gps_never_grants(config,packet_factory,changes):
    assert not GPSEngine(config).assess(replace(packet_factory(),**changes)).valid


def test_timestamp_reversal_and_impossible_jump(config,packet_factory):
    engine=GPSEngine(config); now=datetime.now(timezone.utc)
    engine.assess(packet_factory(timestamp=now),now)
    old=packet_factory(sequence=2,timestamp=now-timedelta(seconds=1))
    assert not engine.assess(old,now).valid
    jump=packet_factory(sequence=3,distance=2000,timestamp=now+timedelta(seconds=1))
    assert not engine.assess(jump,jump.timestamp).valid


def test_cross_trip_history_does_not_confirm(config,packet_factory):
    engine=GPSEngine(config); now=datetime.now(timezone.utc)
    for i in range(4):
        stamp=now+timedelta(seconds=i)
        engine.assess(packet_factory(distance=200-i*10,sequence=i+1,timestamp=stamp),stamp)
    assert not engine.assess(packet_factory(trip_id="NEW",timestamp=now+timedelta(seconds=4)),now+timedelta(seconds=4)).eligible


def test_authentication_replay_and_tampering(config):
    validator=RequestValidator(config,{"AMB-001":"laboratory-test-key"})
    envelope=signed(request(config))
    assert validator.validate(envelope)["requestId"]=="REQ-1"
    with pytest.raises(ValueError,match="duplicate"): validator.validate(envelope)
    envelope["payload"] = envelope["payload"].replace('Critical','Stable')
    with pytest.raises(ValueError,match="authentication"): validator.validate(envelope)


@pytest.mark.parametrize("field,value",[("controllerId","OTHER"),("junctionId","UNKNOWN"),("approachConfidence",79),("speed",0),("latitude",float("nan")),("timestamp","2000-01-01T00:00:00Z")])
def test_bad_requests_rejected(config,field,value):
    data=request(config); data[field]=value
    with pytest.raises(ValueError): RequestValidator(config,{"AMB-001":"laboratory-test-key"}).validate(signed(data))


def test_ack_requires_identity_freshness_and_exact_applied_green(config):
    data=request(config); now=datetime.now(timezone.utc)
    ack={**data,"messageType":"PRIORITY_ACK","accepted":True,"controllerState":"PRIORITY_GREEN",
         "grantedApproach":"NORTH","acknowledgementTimestamp":now.isoformat(),
         "lampState":{s.value:"GREEN" if s==Approach.NORTH else "RED" for s in Approach}}
    assert matching_green_ack(ack,data,now)
    for field,value in [("requestId","OTHER"),("controllerId","OTHER"),("grantedApproach","EAST"),("accepted",False),("controllerState","SAFE_TRANSITION")]:
        assert not matching_green_ack({**ack,field:value},data,now)
    assert not matching_green_ack(ack,data,now+timedelta(seconds=6))
    ack["lampState"]["EAST"]="GREEN"
    assert not matching_green_ack(ack,data,now)


def test_gpio_interlock_latches_and_drives_all_red(config):
    backend=MemoryPins(); driver=GPIODriver(config.raw["gpio"]["pins"],backend)
    signals={s:SignalColour.RED for s in Approach}; signals[Approach.NORTH]=SignalColour.GREEN
    assert driver.apply(signals)==signals
    signals[Approach.EAST]=SignalColour.GREEN
    with pytest.raises(RuntimeError): driver.apply(signals)
    assert driver.fault
    assert all(c==SignalColour.RED for c in driver.applied.values())
    assert all(backend.read(lamps["RED"]) and not backend.read(lamps["GREEN"]) for lamps in driver.pins.values())


def test_readback_fault_detected_even_when_desired_state_unchanged(config):
    backend=MemoryPins(); driver=GPIODriver(config.raw["gpio"]["pins"],backend)
    backend.values[17]=False
    with pytest.raises(RuntimeError): driver.apply(dict(driver.applied))
    assert driver.fault


def test_heartbeat_watchdog_latches():
    clock=[0]; faults=[]; watchdog=Watchdog(2,lambda:faults.append("all-red"),lambda:clock[0])
    clock[0]=1; watchdog.feed(); clock[0]=3
    assert watchdog.check()
    clock[0]=3.01; assert not watchdog.check()
    watchdog.feed(); watchdog.check()
    assert faults==["all-red"]


@pytest.mark.parametrize("side", list(Approach))
def test_cars_stop_queue_then_clear_without_overlap(side):
    engine=TrafficEngine(); lamps={s:SignalColour.RED for s in Approach}
    for i in range(800):
        if i%50==0: engine.spawn(side)
        engine.tick(.05,lamps)
        vehicles=sorted(engine.vehicles,key=lambda v:v.progress)
        assert all(v.progress<engine.STOP for v in vehicles)
        assert all(b.progress-b.length-a.progress >= engine.GAP-1e-6 for a,b in zip(vehicles,vehicles[1:]))
    assert engine.metrics()["queues"][side.value]>1
    assert engine.metrics()["maximumWaitingSeconds"]>0
    lamps[side]=SignalColour.GREEN
    for _ in range(4000): engine.tick(.05,lamps)
    assert engine.cleared==engine.generated and not engine.vehicles


def test_simulation_delta_partition_equivalence():
    a,b=TrafficEngine(),TrafficEngine(); lamps={s:SignalColour.GREEN if s==Approach.NORTH else SignalColour.RED for s in Approach}
    a.spawn(Approach.NORTH); b.spawn(Approach.NORTH)
    a.tick(5,lamps)
    for _ in range(100): b.tick(.05,lamps)
    assert a.vehicles[0].progress==pytest.approx(b.vehicles[0].progress,abs=1e-7)


def test_signed_runtime_applies_output_before_grant(config,packet_factory):
    from raspberry_pi_app.controller_runtime import ControllerRuntime
    runtime=ControllerRuntime(config,"simulation",{"AMB-001":"laboratory-test-key"})
    now=datetime.now(timezone.utc)
    for i in range(4):
        packet=replace(packet_factory(distance=130-10*i,sequence=i+1,timestamp=now-timedelta(seconds=3-i)),request_id="REQ-1")
        runtime.telemetry(json.dumps(signed(packet.to_dict())),"AMB-001")
    assert runtime.coordinator.controller.target_trip_id is None
    data=request(config)
    data.update(latitude=packet.latitude,longitude=packet.longitude,timestamp=packet.timestamp.isoformat())
    runtime.request(signed(data))
    for _ in range(30):
        acks=runtime.tick(.1)
        if acks[0]["controllerState"]=="PRIORITY_GREEN":break
    assert matching_green_ack(acks[0],data,datetime.now(timezone.utc))
    assert runtime.output.applied[Approach.NORTH]==SignalColour.GREEN
    with pytest.raises(ValueError,match="duplicate"):runtime.request(signed(data))


@pytest.mark.parametrize("scenario",range(20))
def test_predefined_component_scenarios(config,scenario):
    from raspberry_pi_app.simulator.scenarios import run_scenario
    result=run_scenario(scenario,config)
    assert result["result"]=="PASS",result


def test_default_single_phase_and_opt_in_paired(config):
    from raspberry_pi_app.core.signal_controller import SignalController
    single=SignalController(config)
    single.tick(config.timing["all_red_seconds"])
    assert sum(c==SignalColour.GREEN for c in single.signals.values())==1
    config.timing.update(normal_cycle_mode="PAIRED",paired_movements=True)
    paired=SignalController(config)
    paired.tick(config.timing["all_red_seconds"])
    assert {s for s,c in paired.signals.items() if c==SignalColour.GREEN}=={Approach.NORTH,Approach.SOUTH}


def test_replay_survives_controller_restart(config,tmp_path):
    store=tmp_path/"replay.json"
    secrets={"AMB-001":"laboratory-test-key"}
    envelope=signed(request(config))
    RequestValidator(config,secrets,store).validate(envelope)
    with pytest.raises(ValueError,match="duplicate"):
        RequestValidator(config,secrets,store).validate(envelope)

def test_hil_adapter_authenticates_and_submits_once(config, packet_factory):
    import json
    from datetime import datetime, timedelta, timezone
    from raspberry_pi_app.controller_runtime import ControllerRuntime
    from raspberry_pi_app.simulator.simulation_adapter import SimulationAdapter
    runtime = ControllerRuntime(config,"simulation",{"AMB-001":"hil-test-secret"})
    published = []
    def publish(topic,payload):
        published.append(topic)
        if topic.endswith("/telemetry2"): runtime.telemetry(payload,"AMB-001")
        elif topic.endswith("/priority"): runtime.request(json.loads(payload))
        else: runtime.cancel(json.loads(payload))
    adapter = SimulationAdapter(config,{"AMB-001":"hil-test-secret"},publish)
    now = datetime.now(timezone.utc)
    for i in range(5):
        adapter.process(packet_factory(distance=150-10*i,sequence=i+1,timestamp=now-timedelta(seconds=4-i)))
    assert len(runtime.requests)==1
    assert sum(topic.endswith("/priority") for topic in published)==1
    assert runtime.coordinator.priority.get("TRIP-1") is not None
    adapter.cancel("TRIP-1")
    assert runtime.coordinator.outcomes["TRIP-1"]=="CANCELLED"
    for _ in range(100): runtime.tick(.1)
    assert runtime.coordinator.controller.target_trip_id is None
    # A new route revision must reconfirm movement; an old completed ID cannot replay.
    adapter = SimulationAdapter(config,{"AMB-001":"hil-test-secret"},publish)
    now=datetime.now(timezone.utc)
    for i in range(4):
        adapter.process(packet_factory(distance=150-10*i,sequence=6+i,timestamp=now-timedelta(seconds=3-i)))
    assert "TRIP-1" not in runtime.coordinator.completed_trips
    assert len(runtime.requests)==1


def test_trip_report_does_not_invent_success():
    from raspberry_pi_app.core.event_logger import EventLogger
    logger=EventLogger()
    logger.record(tripId="trip",eventType="REQUEST_ACCEPTED")
    assert logger.trip_report("trip")["result"]=="INCOMPLETE"
    logger.record(tripId="trip",eventType="JUNCTION_CLEARED")
    logger.record(tripId="trip",eventType="NORMAL_RESTORED")
    assert logger.trip_report("trip")["result"]=="PASS"
    logger.record(tripId="trip",eventType="GPIO_FAULT",failureReason="readback mismatch")
    assert logger.trip_report("trip")["result"]=="FAIL"
    logger.record(tripId="trip",eventType="NOTE",result="<script>alert(1)</script>")
    assert "&lt;script&gt;" in logger.trip_html("trip")
    assert "<script>" not in logger.trip_html("trip")


@pytest.mark.parametrize("inbound",list(Approach))
def test_all_ordinary_vehicle_exits_are_continuous(inbound):
    import math
    from raspberry_pi_app.simulator.vehicle_path import movement_path, position_on_path, OUTBOUND
    for destination in Approach:
        if destination==inbound: continue
        _,_,exit_progress,total=movement_path(inbound,destination)
        previous=position_on_path(inbound,destination,0)
        for progress in range(1,int(total)):
            current=position_on_path(inbound,destination,progress)
            assert math.dist(previous[:2],current[:2]) <= 1.001
            previous=current
        assert position_on_path(inbound,destination,exit_progress)[:2]==pytest.approx(OUTBOUND[destination])
        engine=TrafficEngine(); vehicle=engine.spawn(inbound,destination)
        engine.tick(60,{s:SignalColour.GREEN if s==inbound else SignalColour.RED for s in Approach})
        assert engine.cleared==1 and vehicle.stage.value=="REMOVED"


def test_turning_merge_preserves_spacing():
    import math
    engine=TrafficEngine()
    engine.spawn(Approach.NORTH,Approach.EAST)
    engine.spawn(Approach.WEST,Approach.EAST)
    for _ in range(600):
        engine.tick(.1,{s:SignalColour.GREEN for s in Approach})
        if len(engine.vehicles)==2:
            assert math.dist(engine.vehicles[0].position[:2],engine.vehicles[1].position[:2]) >= 3
    assert engine.cleared==2


def test_hardware_monitor_authenticates_phone_and_ack(config,packet_factory,monkeypatch):
    from types import SimpleNamespace
    from raspberry_pi_app.communication.hardware_monitor import HardwareMonitor
    monkeypatch.setenv("EMERGENCY_WAY_DEVICE_SECRETS",json.dumps({"AMB-001":"laboratory-test-key"}))
    received=[]
    monitor=HardwareMonitor(config,received.append,lambda _:None)
    def send(topic,data):
        monitor._message(None,None,SimpleNamespace(topic=topic,payload=json.dumps(signed(data)).encode()))
    packet=replace(packet_factory(),upcoming_junction_id=config.junction['id'])
    send("lifelane/ambulance/AMB-001/telemetry2",packet.to_dict())
    assert received[-1]["messageType"]=="AUTHENTICATED_TELEMETRY"
    count=len(received)
    send("lifelane/ambulance/AMB-002/telemetry2",packet.to_dict())
    assert len(received)==count
    data=request(config); send(monitor.prefix+"/priority",data)
    ack={**data,"messageType":"PRIORITY_ACK","accepted":True,"mode":"HARDWARE",
         "grantedApproach":"NORTH","controllerState":"PRIORITY_GREEN",
         "lampState":{s.value:"GREEN" if s==Approach.NORTH else "RED" for s in Approach},
         "acknowledgementTimestamp":datetime.now(timezone.utc).isoformat()}
    send(monitor.prefix+"/ack",ack)
    assert received[-1]["verifiedGrant"]
    assert received[-1]["observedResponseSeconds"]>=0
    count=len(received)
    ack["acknowledgementTimestamp"]=(datetime.now(timezone.utc)-timedelta(seconds=8)).isoformat()
    send(monitor.prefix+"/ack",ack)
    assert len(received)==count


def test_registered_turning_ambulance_crosses_correct_exit(config):
    from raspberry_pi_app.simulator.vehicle_path import movement_path
    from raspberry_pi_app.simulator.gps_simulator import SimulatedAmbulance
    from raspberry_pi_app.core.passage_detector import PassageDetector
    points,_,exit_progress,_=movement_path(Approach.NORTH,Approach.EAST)
    config.raw['geometry']['paths']['NORTH']=[[-4,1200]]+points[1:-1]+[[1200,-4]]
    config.raw['geometry']['exit_progress']['NORTH']=exit_progress+1000
    config.raw['geometry']['supported_movements'][0]='NORTH_EAST'
    ambulance=SimulatedAmbulance(config,'SIM-NORTH','TURN',Approach.NORTH,speed_mps=10,signed_distance_metres=300)
    engine=GPSEngine(config); passage=PassageDetector(80)
    eligible=False; cleared=False; now=datetime.now(timezone.utc)
    for i in range(52):
        packet=ambulance.next_packet(now+timedelta(seconds=i))
        if packet is None: break
        assessment=engine.assess(packet,packet.timestamp)
        assert assessment.valid
        eligible |= assessment.eligible
        cleared |= passage.update(assessment)
    assert eligible and cleared
    assert ambulance.exit_side==Approach.EAST
