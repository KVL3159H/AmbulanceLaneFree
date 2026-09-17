"""LifeLane Built-in Lightweight Pure-Python MQTT 3.1.1 Broker.

This module provides a zero-dependency, asyncio-based MQTT 3.1.1 broker designed
specifically for local development and testing of LifeLane (Windows/Pi desktop
simulator + Android mobile client).
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import struct
import sys
from typing import Dict, List, Optional, Set, Tuple

# Set up clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lifelane.broker")

# MQTT Packet Types
CONNECT = 1
CONNACK = 2
PUBLISH = 3
PUBACK = 4
PUBREC = 5
PUBREL = 6
PUBCOMP = 7
SUBSCRIBE = 8
SUBACK = 9
UNSUBSCRIBE = 10
UNSUBACK = 11
PINGREQ = 12
PINGRESP = 13
DISCONNECT = 14


def get_local_ip_addresses() -> List[Tuple[str, str]]:
    """Retrieve local IPv4 addresses with friendly interface descriptions."""
    ips = []
    # Primary outbound IP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            primary_ip = s.getsockname()[0]
            if primary_ip and primary_ip != "127.0.0.1":
                ips.append(("Primary Network / Wi-Fi", primary_ip))
    except Exception:
        pass

    # All hostname IPs
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not any(ip == existing[1] for existing in ips):
                ips.append(("Host Adapter", ip))
    except Exception:
        pass

    if not ips:
        ips.append(("Localhost Only", "127.0.0.1"))
    return ips


def topic_matches(subscription: str, topic: str) -> bool:
    """Check if a published topic matches a subscription filter with + and # wildcards."""
    if subscription == topic:
        return True
    sub_parts = subscription.split("/")
    topic_parts = topic.split("/")

    i = 0
    while i < len(sub_parts):
        sub_p = sub_parts[i]
        if sub_p == "#":
            return True
        if i >= len(topic_parts):
            return False
        topic_p = topic_parts[i]
        if sub_p != "+" and sub_p != topic_p:
            return False
        i += 1

    return i == len(topic_parts)


def encode_remaining_length(length: int) -> bytes:
    """Encode MQTT variable byte integer."""
    encoded = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length > 0:
            digit |= 0x80
        encoded.append(digit)
        if length == 0:
            break
    return bytes(encoded)


async def decode_remaining_length(reader: asyncio.StreamReader) -> int:
    """Decode MQTT variable byte integer from stream."""
    multiplier = 1
    value = 0
    while True:
        byte_data = await reader.readexactly(1)
        byte_val = byte_data[0]
        value += (byte_val & 127) * multiplier
        multiplier *= 128
        if (byte_val & 128) == 0:
            break
        if multiplier > 128 * 128 * 128:
            raise ValueError("Malformed Remaining Length in MQTT header")
    return value


class MQTTClientSession:
    """Represents an active MQTT client connection."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        broker: "PureMQTTBroker",
    ):
        self.reader = reader
        self.writer = writer
        self.broker = broker
        self.client_id: str = "unknown"
        self.subscriptions: Set[str] = set()
        self.peer_addr = writer.get_extra_info("peername")
        self.will_topic: Optional[str] = None
        self.will_message: Optional[bytes] = None
        self.will_qos: int = 0
        self.will_retain: bool = False
        self.clean_session: bool = True
        self.alive = True

    async def send_packet(self, packet_type: int, flags: int, payload: bytes):
        """Build and send a binary MQTT packet."""
        if not self.alive:
            return
        header = bytes([(packet_type << 4) | (flags & 0x0F)])
        rem_len = encode_remaining_length(len(payload))
        data = header + rem_len + payload
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception:
            self.alive = False

    async def run(self):
        """Main processing loop for client connection."""
        try:
            while self.alive:
                first_byte_data = await self.reader.read(1)
                if not first_byte_data:
                    break
                first_byte = first_byte_data[0]
                packet_type = first_byte >> 4
                flags = first_byte & 0x0F
                length = await decode_remaining_length(self.reader)
                body = await self.reader.readexactly(length) if length > 0 else b""

                await self.handle_packet(packet_type, flags, body)
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.debug("Client exception [%s]: %s", self.client_id, e)
        finally:
            await self.close()

    async def handle_packet(self, packet_type: int, flags: int, body: bytes):
        if packet_type == CONNECT:
            await self.handle_connect(flags, body)
        elif packet_type == PUBLISH:
            await self.handle_publish(flags, body)
        elif packet_type == PUBACK:
            pass  # QoS 1 ack received from client
        elif packet_type == SUBSCRIBE:
            await self.handle_subscribe(flags, body)
        elif packet_type == UNSUBSCRIBE:
            await self.handle_unsubscribe(flags, body)
        elif packet_type == PINGREQ:
            await self.send_packet(PINGRESP, 0, b"")
        elif packet_type == DISCONNECT:
            self.will_topic = None  # Normal disconnect suppresses LWT
            self.alive = False

    async def handle_connect(self, flags: int, body: bytes):
        try:
            # Protocol Name
            proto_len = struct.unpack("!H", body[:2])[0]
            offset = 2 + proto_len
            proto_level = body[offset]
            offset += 1
            connect_flags = body[offset]
            offset += 1
            keep_alive = struct.unpack("!H", body[offset : offset + 2])[0]
            offset += 2

            self.clean_session = bool(connect_flags & 0x02)
            has_will = bool(connect_flags & 0x04)
            self.will_qos = (connect_flags >> 3) & 0x03
            self.will_retain = bool(connect_flags & 0x20)
            has_password = bool(connect_flags & 0x40)
            has_username = bool(connect_flags & 0x80)

            # Payload: Client ID
            cid_len = struct.unpack("!H", body[offset : offset + 2])[0]
            offset += 2
            self.client_id = body[offset : offset + cid_len].decode("utf-8", errors="replace")
            offset += cid_len

            if not self.client_id:
                self.client_id = f"anonymous_{self.peer_addr[0]}_{self.peer_addr[1]}"

            # Will topic & payload
            if has_will:
                wt_len = struct.unpack("!H", body[offset : offset + 2])[0]
                offset += 2
                self.will_topic = body[offset : offset + wt_len].decode("utf-8", errors="replace")
                offset += wt_len

                wm_len = struct.unpack("!H", body[offset : offset + 2])[0]
                offset += 2
                self.will_message = body[offset : offset + wm_len]
                offset += wm_len

            logger.info("Client connected: [%s] from %s:%s", self.client_id, self.peer_addr[0], self.peer_addr[1])
            self.broker.register_client(self)

            # Send CONNACK (Return code 0: Connection Accepted)
            connack_payload = bytes([0x00, 0x00])
            await self.send_packet(CONNACK, 0, connack_payload)
        except Exception as e:
            logger.error("Error processing CONNECT from %s: %s", self.peer_addr, e)
            self.alive = False

    async def handle_publish(self, flags: int, body: bytes):
        try:
            dup = bool(flags & 0x08)
            qos = (flags >> 1) & 0x03
            retain = bool(flags & 0x01)

            offset = 0
            topic_len = struct.unpack("!H", body[offset : offset + 2])[0]
            offset += 2
            topic = body[offset : offset + topic_len].decode("utf-8", errors="replace")
            offset += topic_len

            packet_id = None
            if qos > 0:
                packet_id = struct.unpack("!H", body[offset : offset + 2])[0]
                offset += 2

            payload = body[offset:]

            # Acknowledge QoS 1
            if qos == 1 and packet_id is not None:
                await self.send_packet(PUBACK, 0, struct.pack("!H", packet_id))

            # Broadcast to subscribers
            await self.broker.publish(topic, payload, qos=0, retain=retain, sender=self)
        except Exception as e:
            logger.error("Error processing PUBLISH from [%s]: %s", self.client_id, e)

    async def handle_subscribe(self, flags: int, body: bytes):
        try:
            offset = 0
            packet_id = struct.unpack("!H", body[offset : offset + 2])[0]
            offset += 2

            return_codes = []
            while offset < len(body):
                topic_len = struct.unpack("!H", body[offset : offset + 2])[0]
                offset += 2
                topic = body[offset : offset + topic_len].decode("utf-8", errors="replace")
                offset += topic_len
                req_qos = body[offset]
                offset += 1

                self.subscriptions.add(topic)
                return_codes.append(min(req_qos, 1))
                logger.info("[%s] subscribed to '%s'", self.client_id, topic)

                # Send any matching retained messages immediately
                await self.broker.send_retained_to(self, topic)

            # Send SUBACK
            suback_payload = struct.pack("!H", packet_id) + bytes(return_codes)
            await self.send_packet(SUBACK, 0, suback_payload)
        except Exception as e:
            logger.error("Error processing SUBSCRIBE from [%s]: %s", self.client_id, e)

    async def handle_unsubscribe(self, flags: int, body: bytes):
        try:
            offset = 0
            packet_id = struct.unpack("!H", body[offset : offset + 2])[0]
            offset += 2
            while offset < len(body):
                topic_len = struct.unpack("!H", body[offset : offset + 2])[0]
                offset += 2
                topic = body[offset : offset + topic_len].decode("utf-8", errors="replace")
                offset += topic_len
                self.subscriptions.discard(topic)

            await self.send_packet(UNSUBACK, 0, struct.pack("!H", packet_id))
        except Exception as e:
            logger.error("Error processing UNSUBSCRIBE from [%s]: %s", self.client_id, e)

    async def close(self):
        """Tear down connection and publish LWT if needed."""
        self.alive = False
        self.broker.unregister_client(self)
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

        if self.will_topic and self.will_message is not None:
            logger.info("Broadcasting LWT for disconnected client [%s] on '%s'", self.client_id, self.will_topic)
            await self.broker.publish(
                self.will_topic,
                self.will_message,
                qos=self.will_qos,
                retain=self.will_retain,
                sender=None,
            )
            self.will_topic = None


class PureMQTTBroker:
    """Central Asyncio MQTT 3.1.1 Broker."""

    def __init__(self, host: str = "0.0.0.0", port: int = 1883):
        self.host = host
        self.port = port
        self.clients: List[MQTTClientSession] = []
        self.retained_messages: Dict[str, bytes] = {}
        self.server: Optional[asyncio.AbstractServer] = None
        self._packet_counter = 1

    def register_client(self, client: MQTTClientSession):
        self.clients.append(client)

    def unregister_client(self, client: MQTTClientSession):
        if client in self.clients:
            self.clients.remove(client)
            logger.info("Client disconnected: [%s]", client.client_id)

    async def send_retained_to(self, client: MQTTClientSession, sub_topic: str):
        """Send all matching retained messages to a newly subscribed client."""
        for ret_topic, payload in list(self.retained_messages.items()):
            if topic_matches(sub_topic, ret_topic):
                # Build publish packet with retain flag = 1
                topic_bytes = ret_topic.encode("utf-8")
                publish_payload = struct.pack("!H", len(topic_bytes)) + topic_bytes + payload
                await client.send_packet(PUBLISH, 0x01, publish_payload)

    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 0,
        retain: bool = False,
        sender: Optional[MQTTClientSession] = None,
    ):
        """Broadcast a message to all matching subscribers and save retained messages."""
        if retain:
            if len(payload) == 0:
                self.retained_messages.pop(topic, None)
            else:
                self.retained_messages[topic] = payload

        topic_bytes = topic.encode("utf-8")
        packet_payload = struct.pack("!H", len(topic_bytes)) + topic_bytes + payload

        # Deliver to matching clients
        for client in list(self.clients):
            if not client.alive:
                continue
            for sub in client.subscriptions:
                if topic_matches(sub, topic):
                    asyncio.create_task(client.send_packet(PUBLISH, 0x00, packet_payload))
                    break

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        session = MQTTClientSession(reader, writer, self)
        await session.run()

    async def start(self):
        self.server = await asyncio.start_server(self.handle_connection, self.host, self.port)
        logger.info("LifeLane Pure-Python MQTT Broker listening on %s:%d", self.host, self.port)


async def run_broker(host: str = "0.0.0.0", port: int = 1883):
    ips = get_local_ip_addresses()
    primary_ip = ips[0][1] if ips else "127.0.0.1"

    print("=" * 66)
    print("           LIFELANE MQTT BROKER (Zero-Dependency)           ")
    print("=" * 66)
    print(f" Status:       ONLINE & READY on port {port}")
    print(f" Bound to:     {host}:{port} (All Network Interfaces)")
    print("-" * 66)
    print(" Available IP Addresses for your Android App / Hotspot:")
    for label, ip in ips:
        print(f"   * [{label:26s}]  -->  {ip}")
    print("-" * 66)
    print(f" -> For Android Phone (Wi-Fi/Hotspot): set host to {primary_ip}")
    print(f" -> For Android Studio Emulator:       set host to 10.0.2.2")
    print(f" -> For Windows Desktop Simulator:     set host to localhost")
    print("=" * 66)
    print(" Press Ctrl+C at any time to stop the broker.\n")

    # Check if port is already occupied (e.g. system mosquitto)
    sock_test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock_test.settimeout(0.5)
        res = sock_test.connect_ex(("127.0.0.1", port))
        if res == 0:
            logger.warning(
                "Port %d is already bound by another service (e.g. Mosquitto or existing broker).",
                port,
            )
            logger.warning("If an external broker is already running, you can connect directly to it.")
            logger.warning("Otherwise, stop the existing service or choose another port.")
    except Exception:
        pass
    finally:
        sock_test.close()

    broker = PureMQTTBroker(host, port)
    try:
        await broker.start()
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Broker stopped by user.")


def main():
    try:
        asyncio.run(run_broker())
    except KeyboardInterrupt:
        print("\nBroker exited cleanly.")


if __name__ == "__main__":
    main()
