from raspberry_pi_app.core.models import Approach
from raspberry_pi_app.core.signal_controller import SignalController
from raspberry_pi_app.core.signal_states import NormalPhase, PreemptionState, SignalColour


def advance_to_ambulance_green(controller: SignalController, approach=Approach.EAST):
    assert controller.request_preemption(approach, "TRIP-1")
    controller.tick(0.01)  # validation -> pending
    controller.tick(0.01)  # pending -> all red (safe initialization has no active green)
    assert controller.state is PreemptionState.ALL_RED_CLEARANCE
    controller.tick(float(controller.config.timing["all_red_seconds"]))
    assert controller.state is PreemptionState.AMBULANCE_GREEN


def test_normal_traffic_cycle(config):
    controller = SignalController(config)
    controller.tick(1)
    assert controller.normal_phase is NormalPhase.NS_GREEN
    assert controller.signals[Approach.NORTH] is SignalColour.GREEN
    assert controller.signals[Approach.SOUTH] is SignalColour.GREEN
    controller.tick(10)
    assert controller.normal_phase is NormalPhase.NS_YELLOW
    controller.tick(2)
    assert all(value is SignalColour.RED for value in controller.signals.values())
    controller.tick(1)
    assert controller.normal_phase is NormalPhase.EW_GREEN


def test_safe_transition_into_preemption_has_yellow_and_all_red(config):
    seen = []
    controller = SignalController(config, lambda event, message: seen.append((event, message)))
    controller.tick(1)
    controller.tick(4)
    assert controller.request_preemption(Approach.EAST, "TRIP-1")
    controller.tick(0.1)
    controller.tick(0.1)
    assert controller.state is PreemptionState.CLEAR_CURRENT_GREEN
    assert controller.signals[Approach.NORTH] is SignalColour.YELLOW
    controller.tick(2)
    assert controller.state is PreemptionState.ALL_RED_CLEARANCE
    assert all(value is SignalColour.RED for value in controller.signals.values())
    controller.tick(1)
    assert controller.signals[Approach.EAST] is SignalColour.GREEN
    assert sum(value is SignalColour.GREEN for value in controller.signals.values()) == 1


def test_safe_transition_out_of_preemption(config):
    controller = SignalController(config)
    advance_to_ambulance_green(controller)
    controller.mark_passage_complete("TRIP-1")
    controller.tick(0.01)
    assert controller.state is PreemptionState.PASSAGE_MONITORING
    controller.tick(0.01)
    assert controller.state is PreemptionState.RECOVERY_YELLOW
    assert controller.signals[Approach.EAST] is SignalColour.YELLOW
    controller.tick(2)
    assert controller.state is PreemptionState.RECOVERY_ALL_RED
    controller.tick(1)
    assert controller.state is PreemptionState.RETURN_TO_NORMAL
    controller.tick(0.01)
    assert controller.state is PreemptionState.NORMAL
    assert all(value is SignalColour.RED for value in controller.signals.values())


def test_emergency_cancellation(config):
    controller = SignalController(config)
    advance_to_ambulance_green(controller)
    controller.tick(0.01)
    assert controller.cancel_preemption("TRIP-1")
    controller.tick(0.01)
    assert controller.state is PreemptionState.RECOVERY_YELLOW


def test_maximum_green_timeout(config):
    controller = SignalController(config)
    advance_to_ambulance_green(controller)
    controller.tick(0.01)
    controller.tick(float(config.timing["maximum_ambulance_green_seconds"]))
    assert controller.state is PreemptionState.RECOVERY_YELLOW


def test_no_conflicting_green_signals_during_all_transitions(config):
    controller = SignalController(config)
    controller.tick(1)
    controller.tick(4)
    controller.request_preemption(Approach.WEST, "TRIP-1")
    for index in range(80):
        if index == 35:
            controller.mark_passage_complete("TRIP-1")
        controller.tick(0.5)
        greens = {side for side, colour in controller.signals.items() if colour is SignalColour.GREEN}
        assert not (greens & {Approach.NORTH, Approach.SOUTH} and greens & {Approach.EAST, Approach.WEST})


def test_unsafe_state_enters_fail_safe(config):
    controller = SignalController(config)
    controller.force_signals_for_test({
        Approach.NORTH: SignalColour.GREEN,
        Approach.SOUTH: SignalColour.RED,
        Approach.EAST: SignalColour.GREEN,
        Approach.WEST: SignalColour.RED,
    })
    assert controller.state is PreemptionState.FAIL_SAFE
    assert controller.controlled_reset_required
    assert all(value is SignalColour.RED for value in controller.signals.values())


def test_application_restart_safe_initialization(config):
    first = SignalController(config)
    first.tick(1)
    restarted = SignalController(config)
    assert restarted.state is PreemptionState.NORMAL
    assert restarted.normal_phase is NormalPhase.ALL_RED_BEFORE_NS
    assert all(value is SignalColour.RED for value in restarted.signals.values())
