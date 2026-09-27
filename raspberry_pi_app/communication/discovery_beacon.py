"""Zero-Configuration UDP Discovery Beacon for LifeLane.

Broadcasts and responds to LAN discovery probes so Android mobile apps
automatically connect to whatever PC or laptop the broker/simulator is running on,
with ZERO manual IP entry or configuration.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from typing import Optional

LOGGER = logging.getLogger("lifelane.discovery")
DISCOVERY_PORT = 18830


def get_all_lan_ips() -> list[str]:
    """Return all non-loopback IPv4 addresses on this PC."""
    ips = []
    # Primary outbound routing IP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            p = s.getsockname()[0]
            if p and not p.startswith("127."):
                ips.append(p)
    except Exception:
        pass

    # Hostname IPs
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    return ips or ["127.0.0.1"]


class DiscoveryBeacon:
    """Sends periodic UDP broadcast beacons and answers discovery queries."""

    def __init__(self, mqtt_port: int = 1883, web_port: int = 5000) -> None:
        self.mqtt_port = mqtt_port
        self.web_port = web_port
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="DiscoveryBeacon")
        self._thread.start()
        LOGGER.info("LifeLane Auto-Discovery Beacon started on UDP port %d", DISCOVERY_PORT)

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _run(self) -> None:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to listen for incoming search probes
            try:
                self._sock.bind(("", DISCOVERY_PORT))
            except Exception as bind_err:
                LOGGER.debug("Could not bind discovery socket: %s", bind_err)
            self._sock.settimeout(2.0)
        except Exception as exc:
            LOGGER.warning("Discovery socket initialization failed: %s", exc)
            return

        last_broadcast = 0.0

        while self._running:
            now = time.time()
            lan_ips = get_all_lan_ips()
            primary_ip = lan_ips[0]

            # Broadcast every 2.0 seconds
            if now - last_broadcast >= 2.0:
                last_broadcast = now
                beacon_data = json.dumps({
                    "service": "lifelane_broker",
                    "ip": primary_ip,
                    "all_ips": lan_ips,
                    "mqtt_port": self.mqtt_port,
                    "web_port": self.web_port,
                    "hostname": socket.gethostname(),
                    "timestamp": int(now),
                }).encode("utf-8")

                # Broadcast to global broadcast and subnet broadcasts
                destinations = [("255.255.255.255", DISCOVERY_PORT)]
                for ip in lan_ips:
                    parts = ip.split(".")
                    if len(parts) == 4:
                        subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                        if (subnet_bcast, DISCOVERY_PORT) not in destinations:
                            destinations.append((subnet_bcast, DISCOVERY_PORT))

                for dest in destinations:
                    try:
                        self._sock.sendto(beacon_data, dest)
                    except Exception:
                        pass

            # Listen for incoming direct query probes
            try:
                data, addr = self._sock.recvfrom(2048)
                if data and self._running:
                    try:
                        query = json.loads(data.decode("utf-8", errors="replace"))
                        if query.get("query") == "lifelane_discover":
                            reply = json.dumps({
                                "service": "lifelane_broker",
                                "ip": primary_ip,
                                "all_ips": lan_ips,
                                "mqtt_port": self.mqtt_port,
                                "web_port": self.web_port,
                                "hostname": socket.gethostname(),
                            }).encode("utf-8")
                            self._sock.sendto(reply, addr)
                    except Exception:
                        pass
            except socket.timeout:
                continue
            except Exception:
                if not self._running:
                    break


# Global singleton helper
_GLOBAL_BEACON: Optional[DiscoveryBeacon] = None


def start_discovery_beacon(mqtt_port: int = 1883, web_port: int = 5000) -> DiscoveryBeacon:
    global _GLOBAL_BEACON
    if _GLOBAL_BEACON is None or not _GLOBAL_BEACON._running:
        _GLOBAL_BEACON = DiscoveryBeacon(mqtt_port=mqtt_port, web_port=web_port)
        _GLOBAL_BEACON.start()
    return _GLOBAL_BEACON


def stop_discovery_beacon() -> None:
    global _GLOBAL_BEACON
    if _GLOBAL_BEACON is not None:
        _GLOBAL_BEACON.stop()
        _GLOBAL_BEACON = None
