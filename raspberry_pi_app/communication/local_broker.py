"""Owned, in-process broker for the standalone LAN prototype."""
from __future__ import annotations

import asyncio
import socket
import threading

from scripts.run_broker import PureMQTTBroker


class LocalBroker:
    def __init__(self, port: int):
        self.port = port
        self.loop = asyncio.new_event_loop()
        self.broker = PureMQTTBroker(port=port)
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)

    def start(self) -> bool:
        # Leave an existing broker under its original owner's control.
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.3):
                self.loop.close()
                return False
        except OSError:
            pass
        self.thread.start()
        try:
            asyncio.run_coroutine_threadsafe(self.broker.start(), self.loop).result(timeout=3)
        except Exception:
            self.stop()
            raise
        return True

    def stop(self) -> None:
        if not self.thread.is_alive():
            return

        async def shutdown():
            if self.broker.server:
                self.broker.server.close()
            for client in list(self.broker.clients):
                client.will_topic = None
                await client.close()
            tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if self.broker.server:
                await self.broker.server.wait_closed()

        try:
            asyncio.run_coroutine_threadsafe(shutdown(), self.loop).result(timeout=3)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=3)
            if not self.thread.is_alive():
                self.loop.close()
