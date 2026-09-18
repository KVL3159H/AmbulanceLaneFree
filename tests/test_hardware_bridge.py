from __future__ import annotations

import json
from unittest.mock import MagicMock

from raspberry_pi_app.communication.hardware_bridge import HardwareBridge
from raspberry_pi_app.core.models import Approach
from raspberry_pi_app.core.signal_states import PreemptionState, SignalColour


def test_hardware_bridge_initialization():
    bridge = HardwareBridge(port="COM99", baudrate=115200)
    assert bridge.preferred_port == "COM99"
    assert bridge.baudrate == 115200
    assert bridge.connected_port is None


def test_hardware_bridge_send_signals_offline():
    bridge = HardwareBridge(port="COM99")
    signals = {
        Approach.NORTH: SignalColour.GREEN,
        Approach.SOUTH: SignalColour.GREEN,
        Approach.EAST: SignalColour.RED,
        Approach.WEST: SignalColour.RED,
    }
    # Offline should return False safely without crashing
    assert not bridge.send_signals(signals, PreemptionState.NORMAL)


def test_hardware_bridge_send_signals_with_mock_serial():
    bridge = HardwareBridge(port="COM5")
    mock_serial = MagicMock()
    mock_serial.is_open = True
    bridge.serial_conn = mock_serial
    bridge.running = True

    signals = {
        Approach.NORTH: SignalColour.RED,
        Approach.SOUTH: SignalColour.RED,
        Approach.EAST: SignalColour.GREEN,
        Approach.WEST: SignalColour.GREEN,
    }

    success = bridge.send_signals(signals, PreemptionState.AMBULANCE_GREEN, force=True)
    assert success is True
    assert mock_serial.write.called

    written_data = mock_serial.write.call_args[0][0].decode("utf-8")
    assert "SIG:N=RED,S=RED,E=GREEN,W=GREEN,PRE=1" in written_data
