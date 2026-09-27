"""Deterministic longitudinal traffic; metres, seconds and continuous path progress."""
from dataclasses import dataclass
import math

from ..core.models import Approach
from ..core.signal_states import SignalColour
from .vehicle_path import OPPOSITE, movement_path, position_on_path
from ..core.protocol import VehicleStage


@dataclass
class Vehicle:
    vehicle_id: str
    approach: Approach
    progress: float = 0
    speed: float = 0
    acceleration: float = 2
    maximum_speed: float = 12
    length: float = 4.5
    waiting: float = 0
    stage: VehicleStage = VehicleStage.SPAWNED
    destination: Approach | None = None

    @property
    def exit_side(self): return self.destination or OPPOSITE[self.approach]

    @property
    def exit_progress(self): return movement_path(self.approach,self.exit_side)[2]

    @property
    def end_progress(self): return movement_path(self.approach,self.exit_side)[3]

    @property
    def position(self): return position_on_path(self.approach,self.exit_side,self.progress)


class TrafficEngine:
    STOP = 180.0
    EXIT = 220.0
    END = 400.0
    GAP = 3.0
    BRAKE = 4.0

    def __init__(self):
        self.vehicles = []
        self.generated = 0
        self.cleared = 0
        self.elapsed = 0.0
        self.completed_waits = []
        self.running = True
        self.obstacles = []

    def spawn(self, approach, destination=None):
        if destination==approach: raise ValueError("exit must differ from entry approach")
        if any(v.approach == approach and v.progress < v.length + self.GAP for v in self.vehicles):
            return None
        self.generated += 1
        vehicle = Vehicle(f"CAR-{self.generated:04}", approach,destination=destination)
        self.vehicles.append(vehicle)
        return vehicle

    def tick(self, seconds, signals):
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("invalid simulation delta")
        if not self.running:
            return
        # Bounded physics substeps make 5x speed equivalent to real-time operation.
        remaining = seconds
        while remaining > 1e-9:
            dt = min(0.025, remaining)
            self._step(dt, signals)
            remaining -= dt

    def _step(self, dt, signals):
        self.elapsed += dt
        for side in Approach:
            leader = None
            for vehicle in sorted((v for v in self.vehicles+self.obstacles if v.approach == side), key=lambda v: -v.progress):
                if vehicle in self.obstacles:
                    leader = vehicle
                    continue
                limit = float("inf")
                if leader:
                    if vehicle.progress < self.STOP or leader.exit_side==vehicle.exit_side:
                        limit = leader.progress - leader.length - self.GAP
                others=[v for v in self.vehicles+self.obstacles if v is not vehicle]
                # Reserve the conflict zone for turning/conflicting movements. Same
                # straight lane followers keep their longitudinal following rule.
                occupied=any(self.STOP < v.progress < v.exit_progress+v.length+self.GAP and
                    (v.approach!=vehicle.approach or v.exit_side!=vehicle.exit_side or vehicle.exit_side!=OPPOSITE[side]) for v in others)
                if vehicle.progress < self.STOP and occupied: limit=min(limit,self.STOP-.5)
                if vehicle.progress >= self.STOP:
                    for other in others:
                        if other.exit_side==vehicle.exit_side and other.progress>=other.exit_progress:
                            ahead=other.progress-other.exit_progress
                            own=vehicle.progress-vehicle.exit_progress
                            if ahead>own: limit=min(limit,vehicle.exit_progress+ahead-other.length-self.GAP)
                colour = signals[side]
                distance = self.STOP - vehicle.progress
                # The front bumper stops before the line. Yellow may be committed
                # only when stopping would exceed the configured braking rate.
                stop_for_signal = colour is SignalColour.RED or (
                    colour is SignalColour.YELLOW and distance >= vehicle.speed**2/(2*self.BRAKE)+1)
                if distance >= 0 and stop_for_signal:
                    limit = min(limit, self.STOP - 0.5)
                available = max(0, limit-vehicle.progress)
                desired = min(vehicle.maximum_speed, math.sqrt(2*self.BRAKE*available))
                if leader:
                    desired = min(desired, max(0, (available-self.GAP)/1.2))
                old_speed = vehicle.speed
                vehicle.speed = max(0, min(desired, old_speed + vehicle.acceleration*dt))
                previous = vehicle.progress
                vehicle.progress = min(limit, previous + (old_speed+vehicle.speed)*0.5*dt)
                vehicle.progress = max(previous, vehicle.progress)
                if vehicle.progress <= previous + 1e-6:
                    vehicle.speed = 0
                if vehicle.speed < 0.5 and vehicle.progress < self.STOP:
                    vehicle.waiting += dt
                    vehicle.stage = VehicleStage.STOPPED_AT_RED if stop_for_signal else VehicleStage.QUEUED
                elif previous < self.STOP <= vehicle.progress:
                    vehicle.stage = VehicleStage.CROSSING_STOP_LINE
                elif self.STOP <= vehicle.progress <= vehicle.exit_progress:
                    vehicle.stage = VehicleStage.INSIDE_JUNCTION
                elif vehicle.progress > vehicle.exit_progress:
                    vehicle.stage = VehicleStage.EXITING
                else:
                    vehicle.stage = VehicleStage.MOVING_ON_GREEN if colour is SignalColour.GREEN else VehicleStage.APPROACHING
                leader = vehicle
        for vehicle in list(self.vehicles):
            if vehicle.progress - vehicle.length >= vehicle.end_progress:
                vehicle.stage = VehicleStage.CLEARED
                self.cleared += 1
                self.completed_waits.append(vehicle.waiting)
                self.vehicles.remove(vehicle)
                vehicle.stage = VehicleStage.REMOVED

    def metrics(self):
        waits = self.completed_waits + [v.waiting for v in self.vehicles]
        return {
            "generated": self.generated, "cleared": self.cleared,
            "queues": {s.value: sum(v.approach == s and v.progress < self.STOP and v.speed < 0.5 for v in self.vehicles) for s in Approach},
            "averageWaitingSeconds": sum(waits)/len(waits) if waits else 0,
            "maximumWaitingSeconds": max(waits, default=0),
            "averageSpeedMps": sum(v.speed for v in self.vehicles)/len(self.vehicles) if self.vehicles else 0,
            "throughputPerHour": self.cleared*3600/self.elapsed if self.elapsed else 0,
        }
