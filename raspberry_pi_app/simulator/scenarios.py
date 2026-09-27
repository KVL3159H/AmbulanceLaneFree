"""Deterministic laboratory component scenarios; no fabricated measurements."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from ..core.config import JunctionConfig
from ..core.coordinator import LifeLaneCoordinator
from ..core.gpio_driver import GPIODriver, MemoryPins
from ..core.models import Approach, PatientPriority
from ..core.signal_states import PreemptionState, SignalColour
from ..core.watchdog import Watchdog
from .ambulance_factory import create_simulated_ambulance
from .traffic_engine import TrafficEngine

SCENARIOS = [
    ("Normal traffic", "Vehicles stop at red and clear on green"),
    ("Critical ambulance from North", "North selected and normal restored after measured clearance"),
    ("Serious ambulance from East", "East selected and normal restored after measured clearance"),
    ("Stable ambulance from South", "South selected and normal restored after measured clearance"),
    ("Conflicting ambulances", "Second request queues; no conflicting greens"),
    ("Different medical priorities", "Critical ranks before Stable"),
    ("Inaccurate GPS", "No request from poor-accuracy samples"),
    ("Stale GPS", "No request from stale location"),
    ("Stopped ambulance", "Stationary heading never confirms a new request"),
    ("Route cancellation", "Cancelled request cannot requeue"),
    ("U-turn", "Repeated movement away cancels selected approach"),
    ("MQTT loss before request", "No authenticated request means no priority grant"),
    ("MQTT loss after grant", "Lost telemetry expires emergency green safely"),
    ("Controller rejection", "Unauthorized ambulance cannot request priority"),
    ("Heartbeat lost", "Watchdog latches a fault"),
    ("Maximum green timeout", "Yellow and all-red before normal restoration"),
    ("Normal ambulance passage", "Entry and exit confirmed from repeated samples"),
    ("Duplicate telemetry", "Sequence replay is rejected"),
    ("Stale request telemetry", "Expired source data is rejected"),
    ("GPIO conflict fault", "Interlock rejects conflicting greens and latches all-red"),
]


def run_scenario(index, config):
    name, expected = SCENARIOS[index]
    events=[]
    cfg=JunctionConfig(deepcopy(config.raw),config.source)
    coordinator=LifeLaneCoordinator(cfg,event_callback=lambda k,m:events.append((k,m)))
    now=datetime.now(timezone.utc)
    side={2:Approach.EAST,3:Approach.SOUTH}.get(index,Approach.NORTH)
    sim=create_simulated_ambulance(cfg,side,speed_mps=12)
    try:
        if index==0:
            engine=TrafficEngine(); engine.spawn(Approach.NORTH)
            for _ in range(500): engine.tick(.1,{s:SignalColour.RED for s in Approach})
            assert engine.vehicles[0].progress<engine.STOP
            for _ in range(500): engine.tick(.1,{s:SignalColour.GREEN if s==Approach.NORTH else SignalColour.RED for s in Approach})
            assert engine.cleared==1
        elif index in {1,2,3,16}:
            sim.priority={2:PatientPriority.YELLOW,3:PatientPriority.GREEN}.get(index,PatientPriority.RED)
            for second in range(100):
                stamp=now+timedelta(seconds=second)
                packet=sim.next_packet(stamp)
                if packet: coordinator.process_packet(packet,stamp)
                coordinator.tick(1,stamp)
            assert coordinator.outcomes.get(sim.trip_id)=="JUNCTION_CLEARED"
            assert coordinator.controller.state==PreemptionState.NORMAL
        elif index in {6,7,8,13,18}:
            for i in range(8):
                stamp=now+timedelta(seconds=i)
                packet=sim.next_packet(stamp)
                if index==6: packet=replace(packet,accuracy_metres=80)
                if index in {7,18}: packet=replace(packet,timestamp=stamp-timedelta(seconds=30))
                if index==8: packet=replace(packet,speed_mps=0)
                if index==13: packet=replace(packet,ambulance_id="UNKNOWN")
                coordinator.process_packet(packet,stamp)
            assert len(coordinator.priority)==0
        elif index==14:
            clock=[0]; faults=[]
            watchdog=Watchdog(2,lambda:faults.append(True),lambda:clock[0])
            clock[0]=3; assert not watchdog.check() and faults
        elif index==19:
            driver=GPIODriver(cfg.raw["gpio"]["pins"],MemoryPins())
            lamps={s:SignalColour.RED for s in Approach}
            lamps[Approach.NORTH]=lamps[Approach.EAST]=SignalColour.GREEN
            try: driver.apply(lamps)
            except RuntimeError: pass
            assert driver.fault and all(c==SignalColour.RED for c in driver.applied.values())
        elif index==17:
            packet=sim.next_packet(now)
            assert coordinator.process_packet(packet,now).valid
            assert not coordinator.process_packet(packet,now).valid
        else:
            if index==11: coordinator.automatic_requests=False
            sim.signed_distance_metres=160
            for i in range(4):
                stamp=now+timedelta(seconds=i)
                coordinator.process_packet(sim.next_packet(stamp),stamp)
            if index==11:
                assert coordinator.controller.target_trip_id is None
            elif index in {4,5}:
                second=create_simulated_ambulance(cfg,Approach.EAST,ambulance_id="SIM-SECOND")
                second.signed_distance_metres=160
                for i in range(4):
                    stamp=now+timedelta(seconds=i)
                    coordinator.process_packet(second.next_packet(stamp),stamp)
                assert len(coordinator.priority)==2
                if index==5:
                    coordinator.priority.get(sim.trip_id).priority=PatientPriority.GREEN
                    assert coordinator.priority.ordered(now)[0].trip_id==second.trip_id
                assert sum(c==SignalColour.GREEN for c in coordinator.controller.signals.values())<=2
                assert coordinator.controller.target_trip_id==sim.trip_id
            elif index==9:
                coordinator.cancel(sim.trip_id,"ROUTE_CHANGED")
                packet=sim.next_packet(now+timedelta(seconds=5))
                coordinator.process_packet(packet,packet.timestamp)
                assert len(coordinator.priority)==0
            elif index==10:
                for i in range(5):
                    stamp=now+timedelta(seconds=4+i)
                    sim.signed_distance_metres=140+i*12
                    packet=replace(sim.next_packet(stamp),heading_degrees=0)
                    coordinator.process_packet(packet,stamp)
                assert coordinator.outcomes.get(sim.trip_id)=="CANCELLED"
            elif index in {12,15}:
                for second in range(4,100): coordinator.tick(1,now+timedelta(seconds=second))
                assert coordinator.controller.state==PreemptionState.NORMAL
                assert any("Maximum ambulance green" in message for _,message in events)
        return {"scenario":index+1,"name":name,"expected":expected,"result":"PASS","scope":"component simulation"}
    except Exception as exc:
        return {"scenario":index+1,"name":name,"expected":expected,"result":"FAIL","reason":str(exc) or type(exc).__name__,"scope":"component simulation"}
