"""Lightweight pure-Python MQTT broker for LifeLane."""

import asyncio
import logging
from amqtt.broker import Broker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("lifelane.broker")

CONFIG = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        }
    },
    "sys_interval": 0,
    "auth": {
        "allow-anonymous": True,
    }
}

async def main():
    broker = Broker(CONFIG)
    await broker.start()
    logger.info("========================================================")
    logger.info("  LifeLane MQTT Broker is RUNNING on port 1883")
    logger.info("  Listening on 0.0.0.0:1883 (accepts phone and PC)")
    logger.info("  Press Ctrl+C to stop the broker")
    logger.info("========================================================")
    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutting down broker...")
        await broker.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
