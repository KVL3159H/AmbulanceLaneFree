"""Complete-state GPIO interlock. Readback verifies pin logic, not lamp current."""
from threading import RLock
from .models import Approach
from .signal_states import SignalColour
from .safety_validator import assert_safe, UnsafeSignalState


class MemoryPins:
    def __init__(self):
        self.values = {}

    def write(self, pin, value):
        self.values[pin] = bool(value)

    def read(self, pin):
        return self.values.get(pin, False)


class GPIOZeroPins:
    def __init__(self, pins):
        import os
        from gpiozero import DigitalOutputDevice
        from gpiozero.pins.lgpio import LGPIOFactory
        chip = os.getenv("EMERGENCY_WAY_GPIO_CHIP")
        self.factory = LGPIOFactory(chip=int(chip)) if chip is not None else LGPIOFactory()
        self.devices = {pin: DigitalOutputDevice(pin, initial_value=False, pin_factory=self.factory) for pin in pins}

    def write(self, pin, value):
        self.devices[pin].value = value

    def read(self, pin):
        return bool(self.devices[pin].value)


class GPIODriver:
    def __init__(self, pins, backend, paired=False):
        self.pins = pins
        self.backend = backend
        self.paired = paired
        self.lock = RLock()
        self.fault = False
        flattened = [p for lamps in pins.values() for p in lamps.values()]
        if set(pins) != {s.value for s in Approach} or len(flattened) != 12 or len(set(flattened)) != 12:
            raise ValueError("exactly twelve distinct configured lamp pins required")
        if any(set(lamps) != {c.value for c in SignalColour} for lamps in pins.values()):
            raise ValueError("each approach requires RED, YELLOW and GREEN")
        self.applied = {}
        self.all_red()
        self._verify(self.applied)

    def all_red(self):
        with self.lock:
            # Disable every permissive output before energising red.
            for lamps in self.pins.values():
                for colour in ("GREEN", "YELLOW"):
                    self.backend.write(lamps[colour], False)
            for lamps in self.pins.values():
                self.backend.write(lamps["RED"], True)
            self.applied = {s: SignalColour.RED for s in Approach}

    def apply(self, signals):
        with self.lock:
            try:
                if self.fault:
                    raise UnsafeSignalState("output fault is latched; controlled recovery required")
                assert_safe(signals)
                if not self.paired and sum(c is SignalColour.GREEN for c in signals.values()) > 1:
                    raise UnsafeSignalState("single-approach model rejects paired green")
                if any(not isinstance(c, SignalColour) for c in signals.values()):
                    raise UnsafeSignalState("unknown lamp colour")
                if signals == self.applied:
                    self._verify(signals)
                    return dict(self.applied)
                self.all_red()
                for side, colour in signals.items():
                    if colour is not SignalColour.RED:
                        self.backend.write(self.pins[side.value]["RED"], False)
                        self.backend.write(self.pins[side.value][colour.value], True)
                self._verify(signals)
                self.applied = dict(signals)
                return dict(self.applied)
            except Exception:
                self.fault = True
                self.all_red()
                raise

    def _verify(self, signals):
        for side, colour in signals.items():
            for name, pin in self.pins[side.value].items():
                if self.backend.read(pin) != (name == colour.value):
                    raise UnsafeSignalState("GPIO readback mismatch")
