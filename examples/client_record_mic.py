#!/usr/bin/env python3
"""示例客户端 — 开始/停止降噪麦克风录音。

用法：
    # 先启动桥服务
    source /opt/ros/humble/setup.bash
    PYTHONPATH=. python3 -m bridge.main

    # 再运行本客户端，默认录制 25 秒
    python3 examples/client_record_mic.py
    python3 examples/client_record_mic.py --uri ws://localhost:8765 --duration 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("record_mic_demo")

_REQ_ID = 0


def _next_id() -> int:
    global _REQ_ID
    _REQ_ID += 1
    return _REQ_ID


async def call_rpc(ws, method: str, params: dict[str, Any] | None = None) -> dict:
    request = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": method,
        "params": params or {},
    }
    raw = json.dumps(request, ensure_ascii=False)
    logger.info("-> %s", raw)
    await ws.send(raw)

    while True:
        resp_raw = await ws.recv()
        resp = json.loads(resp_raw)
        if "id" not in resp:
            logger.info("<- notification: %s", json.dumps(resp, ensure_ascii=False))
            continue
        logger.info("<- %s", json.dumps(resp, ensure_ascii=False))
        return resp


def _require_result(resp: dict, method: str) -> dict:
    if "error" in resp:
        raise RuntimeError(f"{method} failed: {resp['error']}")
    return resp.get("result") or {}


async def main(uri: str, duration: float) -> None:
    async with websockets.connect(uri) as ws:
        logger.info("Connected to %s", uri)

        start = _require_result(
            await call_rpc(ws, "mic.record_start"),
            "mic.record_start",
        )
        print(f"Recording started: {start.get('path')}")

        await asyncio.sleep(duration)

        status = _require_result(
            await call_rpc(ws, "mic.record_status"),
            "mic.record_status",
        )
        print(
            "Recording status: "
            f"duration={status.get('duration_sec')}s "
            f"frames={status.get('frames_written')}"
        )

        stop = _require_result(
            await call_rpc(ws, "mic.record_stop"),
            "mic.record_stop",
        )
        print(f"Recording stopped: {stop.get('path')}")
        print(f"Saved WAV duration: {stop.get('duration_sec')}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record denoised mic audio through bridge")
    parser.add_argument("--uri", default="ws://localhost:8765", help="Bridge WebSocket URI")
    parser.add_argument("--duration", type=float, default=25.0, help="Recording duration in seconds")
    args = parser.parse_args()
    asyncio.run(main(args.uri, args.duration))
