"""Traffic-signal safety invariant checks."""

from __future__ import annotations

from .models import Approach
from .signal_states import SignalColour


class UnsafeSignalState(RuntimeError):
    pass


def conflicting_green(signals: dict[Approach, SignalColour]) -> bool:
    greens = {side for side, colour in signals.items() if colour is SignalColour.GREEN}
    ns = bool(greens.intersection({Approach.NORTH, Approach.SOUTH}))
    ew = bool(greens.intersection({Approach.EAST, Approach.WEST}))
    return ns and ew


def assert_safe(signals: dict[Approach, SignalColour]) -> None:
    if set(signals) != set(Approach):
        raise UnsafeSignalState("signal state must contain all four approaches")
    if conflicting_green(signals):
        raise UnsafeSignalState("conflicting north/south and east/west greens detected")
