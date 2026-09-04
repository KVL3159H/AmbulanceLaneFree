"""Deterministic normal-cycle and ambulance-preemption finite state machine."""

from __future__ import annotations

from collections.abc import Callable

from .config import JunctionConfig
from .models import Approach
from .safety_validator import UnsafeSignalState, assert_safe
from .signal_states import NormalPhase, PreemptionState, SignalColour

EventCallback = Callable[[str, str], None]


class SignalController:
    def __init__(self, config: JunctionConfig, event_callback: EventCallback | None = None) -> None:
        self.config = config
        self.event_callback = event_callback or (lambda _event, _reason: None)
        self.state = PreemptionState.NORMAL
        self.normal_phase = NormalPhase.ALL_RED_BEFORE_NS
        self.signals = {side: SignalColour.RED for side in Approach}
        self.elapsed = 0.0
        self.running = True
        self.target_approach: Approach | None = None
        self.target_trip_id: str | None = None
        self.controlled_reset_required = False
        self._passage_complete = False
        self._cancel_requested = False
        self._pending_minimum_green = 0.0
        self._check_safety()

    def start(self) -> None:
        if not self.controlled_reset_required:
            self.running = True
            self.event_callback("CYCLE_STARTED", "Normal traffic cycle started")

    def pause(self) -> None:
        self.running = False
        self.event_callback("CYCLE_PAUSED", "Signal timing paused")

    def reset(self) -> None:
        self.state = PreemptionState.NORMAL
        self.normal_phase = NormalPhase.ALL_RED_BEFORE_NS
        self.signals = {side: SignalColour.RED for side in Approach}
        self.elapsed = 0.0
        self.running = True
        self.target_approach = None
        self.target_trip_id = None
        self.controlled_reset_required = False
        self._passage_complete = False
        self._cancel_requested = False
        self._pending_minimum_green = 0.0
        self._check_safety()
        self.event_callback("CONTROLLED_RESET", "Safe all-red initialization complete")

    def request_preemption(self, approach: Approach, trip_id: str) -> bool:
        if self.state is not PreemptionState.NORMAL or self.controlled_reset_required:
            return False
        if SignalColour.GREEN in self.signals.values():
            minimum = float(self.config.timing["minimum_green_seconds"])
            self._pending_minimum_green = max(0.0, minimum - self.elapsed)
        else:
            self._pending_minimum_green = 0.0
        self.target_approach = approach
        self.target_trip_id = trip_id
        self._set_state(PreemptionState.REQUEST_VALIDATION, "Priority request received")
        return True

    def cancel_preemption(self, trip_id: str | None = None) -> bool:
        if trip_id and trip_id != self.target_trip_id:
            return False
        if self.state is PreemptionState.NORMAL:
            return False
        self._cancel_requested = True
        self.event_callback("EMERGENCY_CANCELLED", "Selected emergency was cancelled")
        return True

    def mark_passage_complete(self, trip_id: str) -> bool:
        if trip_id != self.target_trip_id:
            return False
        if self.state in {PreemptionState.AMBULANCE_GREEN, PreemptionState.PASSAGE_MONITORING}:
            self._passage_complete = True
            return True
        return False

    def tick(self, seconds: float) -> None:
        if not self.running or self.controlled_reset_required:
            return
        self.elapsed += max(0.0, seconds)
        try:
            if self.state is PreemptionState.NORMAL:
                self._tick_normal()
            else:
                self._tick_preemption()
            self._check_safety()
        except UnsafeSignalState as exc:
            self._enter_fail_safe(str(exc))

    def force_signals_for_test(self, signals: dict[Approach, SignalColour]) -> None:
        """Test/diagnostic hook which still invokes the production invariant."""
        self.signals = dict(signals)
        try:
            self._check_safety()
        except UnsafeSignalState as exc:
            self._enter_fail_safe(str(exc))

    def _tick_normal(self) -> None:
        timing = self.config.timing
        duration = {
            NormalPhase.NS_GREEN: float(timing["normal_green_seconds"]),
            NormalPhase.NS_YELLOW: float(timing["yellow_seconds"]),
            NormalPhase.ALL_RED_BEFORE_EW: float(timing["all_red_seconds"]),
            NormalPhase.EW_GREEN: float(timing["normal_green_seconds"]),
            NormalPhase.EW_YELLOW: float(timing["yellow_seconds"]),
            NormalPhase.ALL_RED_BEFORE_NS: float(timing["all_red_seconds"]),
        }[self.normal_phase]
        if self.elapsed < duration:
            return
        next_phase = {
            NormalPhase.ALL_RED_BEFORE_NS: NormalPhase.NS_GREEN,
            NormalPhase.NS_GREEN: NormalPhase.NS_YELLOW,
            NormalPhase.NS_YELLOW: NormalPhase.ALL_RED_BEFORE_EW,
            NormalPhase.ALL_RED_BEFORE_EW: NormalPhase.EW_GREEN,
            NormalPhase.EW_GREEN: NormalPhase.EW_YELLOW,
            NormalPhase.EW_YELLOW: NormalPhase.ALL_RED_BEFORE_NS,
        }[self.normal_phase]
        self.normal_phase = next_phase
        self.elapsed = 0.0
        self._apply_normal_phase()
        self.event_callback("NORMAL_PHASE", next_phase.value)

    def _tick_preemption(self) -> None:
        timing = self.config.timing
        if self.state is PreemptionState.REQUEST_VALIDATION:
            self._set_state(PreemptionState.PREEMPTION_PENDING, "Request validation passed")
        elif self.state is PreemptionState.PREEMPTION_PENDING:
            if self.elapsed >= self._pending_minimum_green:
                self._begin_clearance()
        elif self.state is PreemptionState.CLEAR_CURRENT_GREEN:
            if self.elapsed >= float(timing["yellow_seconds"]):
                self._set_all_red()
                self._set_state(PreemptionState.ALL_RED_CLEARANCE, "Conflicting traffic cleared")
        elif self.state is PreemptionState.ALL_RED_CLEARANCE:
            if self.elapsed >= float(timing["all_red_seconds"]):
                if self._cancel_requested:
                    self._set_state(PreemptionState.RETURN_TO_NORMAL, "Cancelled during clearance")
                else:
                    self._grant_ambulance_green()
        elif self.state is PreemptionState.AMBULANCE_GREEN:
            self._set_state(PreemptionState.PASSAGE_MONITORING, "Monitoring ambulance passage")
        elif self.state is PreemptionState.PASSAGE_MONITORING:
            timed_out = self.elapsed >= float(timing["maximum_ambulance_green_seconds"])
            if self._passage_complete or self._cancel_requested or timed_out:
                reason = "Ambulance crossed" if self._passage_complete else (
                    "Emergency cancelled" if self._cancel_requested else "Maximum ambulance green reached"
                )
                self._begin_recovery(reason)
        elif self.state is PreemptionState.RECOVERY_YELLOW:
            if self.elapsed >= float(timing["yellow_seconds"]):
                self._set_all_red()
                self._set_state(PreemptionState.RECOVERY_ALL_RED, "Recovery yellow complete")
        elif self.state is PreemptionState.RECOVERY_ALL_RED:
            if self.elapsed >= float(timing["all_red_seconds"]):
                self._set_state(PreemptionState.RETURN_TO_NORMAL, "Recovery all-red complete")
        elif self.state is PreemptionState.RETURN_TO_NORMAL:
            self.state = PreemptionState.NORMAL
            self.normal_phase = NormalPhase.ALL_RED_BEFORE_NS
            self._set_all_red()
            self.elapsed = 0.0
            completed_trip = self.target_trip_id
            self.target_approach = None
            self.target_trip_id = None
            self._passage_complete = False
            self._cancel_requested = False
            self._pending_minimum_green = 0.0
            self.event_callback("NORMAL_RESTORED", f"Normal cycle restored after {completed_trip or 'request'}")

    def _begin_clearance(self) -> None:
        active_colours = set(self.signals.values())
        if SignalColour.GREEN in active_colours:
            self.signals = {
                side: SignalColour.YELLOW if colour is SignalColour.GREEN else SignalColour.RED
                for side, colour in self.signals.items()
            }
            self._set_state(PreemptionState.CLEAR_CURRENT_GREEN, "Preemption clearance started")
        elif SignalColour.YELLOW in active_colours:
            self.signals = {
                side: SignalColour.YELLOW if colour is SignalColour.YELLOW else SignalColour.RED
                for side, colour in self.signals.items()
            }
            self._set_state(PreemptionState.CLEAR_CURRENT_GREEN, "Existing yellow clearance retained")
        else:
            self._set_all_red()
            self._set_state(PreemptionState.ALL_RED_CLEARANCE, "Junction already all red")

    def _grant_ambulance_green(self) -> None:
        if self.target_approach is None:
            self._enter_fail_safe("No target approach for ambulance green")
            return
        self.signals = {
            side: SignalColour.GREEN if side is self.target_approach else SignalColour.RED
            for side in Approach
        }
        self._set_state(PreemptionState.AMBULANCE_GREEN, f"{self.target_approach.value} signal granted green")
        self.event_callback("AMBULANCE_GREEN", self.target_approach.value)

    def _begin_recovery(self, reason: str) -> None:
        self.signals = {
            side: SignalColour.YELLOW if colour is SignalColour.GREEN else SignalColour.RED
            for side, colour in self.signals.items()
        }
        self._set_state(PreemptionState.RECOVERY_YELLOW, reason)

    def _apply_normal_phase(self) -> None:
        red = {side: SignalColour.RED for side in Approach}
        if self.normal_phase is NormalPhase.NS_GREEN:
            red[Approach.NORTH] = red[Approach.SOUTH] = SignalColour.GREEN
        elif self.normal_phase is NormalPhase.NS_YELLOW:
            red[Approach.NORTH] = red[Approach.SOUTH] = SignalColour.YELLOW
        elif self.normal_phase is NormalPhase.EW_GREEN:
            red[Approach.EAST] = red[Approach.WEST] = SignalColour.GREEN
        elif self.normal_phase is NormalPhase.EW_YELLOW:
            red[Approach.EAST] = red[Approach.WEST] = SignalColour.YELLOW
        self.signals = red

    def _set_all_red(self) -> None:
        self.signals = {side: SignalColour.RED for side in Approach}

    def _set_state(self, state: PreemptionState, reason: str) -> None:
        previous = self.state
        self.state = state
        self.elapsed = 0.0
        self._check_safety()
        self.event_callback("STATE_TRANSITION", f"{previous.value} → {state.value}: {reason}")

    def _check_safety(self) -> None:
        assert_safe(self.signals)

    def _enter_fail_safe(self, reason: str) -> None:
        previous = self.state
        self._set_all_red()
        self.state = PreemptionState.FAIL_SAFE
        self.running = False
        self.controlled_reset_required = True
        self.elapsed = 0.0
        self.event_callback("CRITICAL_FAIL_SAFE", f"{previous.value}: {reason}; all signals forced red")
