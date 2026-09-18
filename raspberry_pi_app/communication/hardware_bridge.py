"""Hardware Serial Bridge for physical traffic signal hardware.

Communicates with ESP32/microcontroller prototypes over USB data cable
(or GPIO UART on Raspberry Pi) to physically actuate Red, Yellow, and Green LEDs
in lockstep with LifeLane's signal controller.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

from ..core.models import Approach
from ..core.signal_states import PreemptionState, SignalColour

logger = logging.getLogger("lifelane.hardware")

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    SERIAL_AVAILABLE = False


class HardwareBridge:
    """Manages auto-connecting and sending real-time signal states to ESP32."""

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        status_callback: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        self.preferred_port = port
        self.baudrate = baudrate
        self.status_callback = status_callback
        self.connected_port: str | None = None
        self.serial_conn: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        self.running = False
        self._thread: Optional[threading.Thread] = None

        self._last_sent_str = ""
        self._last_send_time = 0.0

    @classmethod
    def list_available_ports(cls) -> list[str]:
        """Return list of candidate USB/UART serial ports."""
        if not SERIAL_AVAILABLE:
            return []
        try:
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    def find_best_port(self) -> str | None:
        """Auto-detect ESP32 / USB-Serial bridge (CP210x, CH340, FTDI, etc.)."""
        if not SERIAL_AVAILABLE:
            return None

        if self.preferred_port:
            return self.preferred_port

        try:
            ports = list(serial.tools.list_ports.comports())
            if not ports:
                return None

            # Look for common USB-UART descriptors (like user's CP210x on COM5)
            for p in ports:
                desc = (p.description or "").lower()
                name = (p.name or "").lower()
                if any(kw in desc or kw in name for kw in ["cp210", "ch340", "ftdi", "usb serial", "uart", "esp32"]):
                    return p.device

            # Fallback to the first available port
            return ports[0].device
        except Exception as err:
            logger.debug("Error probing serial ports: %s", err)
            return None

    def start(self) -> None:
        """Start the background serial connection manager."""
        if not SERIAL_AVAILABLE:
            logger.warning("pyserial is not installed. Hardware traffic light bridge disabled.")
            if self.status_callback:
                self.status_callback(False, "pyserial not installed")
            return

        self.running = True
        self._thread = threading.Thread(target=self._connection_loop, daemon=True, name="HardwareBridgeThread")
        self._thread.start()

    def stop(self) -> None:
        """Stop connection and close port."""
        self.running = False
        with self.lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
                self.serial_conn = None
        self.connected_port = None
        if self.status_callback:
            self.status_callback(False, "Disconnected")

    def _connection_loop(self) -> None:
        """Keep connection alive or reconnect if cable is unplugged."""
        while self.running:
            if self.serial_conn is None or not self.serial_conn.is_open:
                target = self.find_best_port()
                if target:
                    try:
                        conn = serial.Serial(target, self.baudrate, timeout=0.2)
                        with self.lock:
                            self.serial_conn = conn
                            self.connected_port = target
                        logger.info("Hardware traffic light connected on %s @ %d baud", target, self.baudrate)
                        if self.status_callback:
                            self.status_callback(True, target)
                    except Exception as exc:
                        logger.debug("Could not open port %s: %s", target, exc)
                        if self.status_callback:
                            self.status_callback(False, f"Offline ({exc.__class__.__name__})")
                else:
                    if self.status_callback:
                        self.status_callback(False, "No hardware detected")

            # Read any ACKs non-blocking
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    while self.serial_conn.in_waiting:
                        line = self.serial_conn.readline().decode("utf-8", errors="ignore").strip()
                        if line:
                            logger.debug("ESP32 response: %s", line)
                except Exception:
                    # Port closed or cable unplugged
                    self._handle_disconnect()

            time.sleep(1.0)

    def _handle_disconnect(self) -> None:
        with self.lock:
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
                self.serial_conn = None
        port = self.connected_port
        self.connected_port = None
        logger.warning("Hardware traffic light on %s disconnected", port)
        if self.status_callback:
            self.status_callback(False, "Cable unplugged")

    def send_signals(
        self,
        signals: dict[Approach, SignalColour],
        preemption_state: PreemptionState | str,
        force: bool = False,
    ) -> bool:
        """Send signal states to ESP32 over serial.

        Payload contains individual approach states, as well as combined NS and EW.
        """
        if not self.running or self.serial_conn is None or not self.serial_conn.is_open:
            return False

        # Extract values
        ns_color = signals.get(Approach.NORTH, SignalColour.RED).value
        ew_color = signals.get(Approach.EAST, SignalColour.RED).value
        preempt_active = (
            preemption_state not in (PreemptionState.NORMAL, PreemptionState.FAIL_SAFE, "NORMAL", "FAIL_SAFE")
        )

        packet = {
            "type": "signals",
            "NORTH": signals.get(Approach.NORTH, SignalColour.RED).value,
            "SOUTH": signals.get(Approach.SOUTH, SignalColour.RED).value,
            "EAST": signals.get(Approach.EAST, SignalColour.RED).value,
            "WEST": signals.get(Approach.WEST, SignalColour.RED).value,
            "ns": ns_color,
            "ew": ew_color,
            "preemption": preemption_state.value if hasattr(preemption_state, "value") else str(preemption_state),
            "preempt": 1 if preempt_active else 0,
        }
        line = json.dumps(packet) + "\n"

        now = time.time()
        # Avoid redundant serial traffic unless state changed or 1.5s heartbeat elapsed
        if not force and line == self._last_sent_str and (now - self._last_send_time) < 1.5:
            return True

        with self.lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.write(line.encode("utf-8"))
                    self.serial_conn.flush()
                    self._last_sent_str = line
                    self._last_send_time = now
                    return True
                except Exception as err:
                    logger.warning("Error writing to serial hardware: %s", err)
                    self._handle_disconnect()
                    return False
        return False
