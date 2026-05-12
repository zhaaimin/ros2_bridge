#!/usr/bin/env python3
"""WebSocket JSON-RPC → ROS2 桥接服务入口。

用法：
    python3 -m bridge.main
    python3 -m bridge.main --host 0.0.0.0 --port 8765
"""

import argparse
import asyncio
import logging
import sys

from bridge.handlers.battery import setup_default_battery_subscription
from bridge.ros2_adapter import Ros2Adapter
from bridge.server import BridgeServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WebSocket JSON-RPC → ROS2 bridge")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


async def _main(host: str, port: int) -> None:
    loop = asyncio.get_running_loop()

    adapter = Ros2Adapter()
    adapter.start_in_thread(loop)

    logger.info("Waiting for ROS2 node to initialize…")
    if not adapter.wait_ready(timeout=10.0):
        logger.error("ROS2 node failed to initialize within 10 s — is ROS2 sourced?")
        sys.exit(1)

    logger.info("ROS2 node ready")
    server = BridgeServer(adapter)
    setup_default_battery_subscription(adapter, server, loop)
    await server.serve(host, port)


def main() -> None:
    args = parse_args()
    asyncio.run(_main(args.host, args.port))


if __name__ == "__main__":
    main()
