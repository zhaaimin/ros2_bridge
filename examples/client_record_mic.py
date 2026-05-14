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
_MIC_TOPIC = "/sys/speech/mic_denoise"


def _next_id() -> int:
    global _REQ_ID
    _REQ_ID += 1
    return _REQ_ID


async def read_messages(ws, pending: dict[int, asyncio.Future], stats: dict[str, Any]) -> None:
    async for resp_raw in ws:
        msg = json.loads(resp_raw)
        if "id" in msg:
            future = pending.pop(msg["id"], None)
            if future is not None and not future.done():
                future.set_result(msg)
            else:
                logger.info("<- unmatched response: %s", json.dumps(msg, ensure_ascii=False))
            continue

        if msg.get("method") == "mic.data":
            params = msg.get("params") or {}
            stats["mic_frames"] += 1
            stats["last_seq"] = params.get("seq")
            stats["dropped_count"] = params.get("dropped_count", 0)
            if stats["mic_frames"] == 1 or stats["mic_frames"] % 100 == 0:
                logger.info(
                    "<- mic.data frames=%d seq=%s dropped=%s samples=%d",
                    stats["mic_frames"],
                    stats["last_seq"],
                    stats["dropped_count"],
                    len(params.get("data", [])),
                )
        else:
            logger.info("<- notification: %s", json.dumps(msg, ensure_ascii=False))


async def call_rpc(
    ws,
    pending: dict[int, asyncio.Future],
    method: str,
    params: dict[str, Any] | None = None,
) -> dict:
    req_id = _next_id()
    request = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }
    raw = json.dumps(request, ensure_ascii=False)
    logger.info("-> %s", raw)
    future = asyncio.get_running_loop().create_future()
    pending[req_id] = future
    await ws.send(raw)
    resp = await future
    logger.info("<- %s", json.dumps(resp, ensure_ascii=False))
    return resp


def _require_result(resp: dict, method: str) -> dict:
    if "error" in resp:
        raise RuntimeError(f"{method} failed: {resp['error']}")
    return resp.get("result") or {}


async def main(uri: str, duration: float) -> None:
    async with websockets.connect(uri) as ws:
        logger.info("Connected to %s", uri)
        pending: dict[int, asyncio.Future] = {}
        stats: dict[str, Any] = {
            "mic_frames": 0,
            "last_seq": None,
            "dropped_count": 0,
        }
        reader = asyncio.create_task(read_messages(ws, pending, stats))

        try:
            subscribed = _require_result(
                await call_rpc(ws, pending, "mic.subscribe", {"topic": _MIC_TOPIC}),
                "mic.subscribe",
            )
            print(f"Subscribed mic topic: {subscribed.get('topic')}")

            start = _require_result(
                await call_rpc(ws, pending, "mic.record_start"),
                "mic.record_start",
            )
            print(f"Recording started: {start.get('path')}")

            await asyncio.sleep(duration)

            # status = _require_result(
            #     await call_rpc(ws, pending, "mic.record_status"),
            #     "mic.record_status",
            # )
            # print(
            #     "Recording status: "
            #     f"duration={status.get('duration_sec')}s "
            #     f"frames={status.get('frames_written')}"
            # )

            stop = _require_result(
                await call_rpc(ws, pending, "mic.record_stop"),
                "mic.record_stop",
            )
            print(f"Recording stopped: {stop.get('path')}")
            print(f"Saved WAV duration: {stop.get('duration_sec')}s")
            print(
                "Received mic notifications: "
                f"frames={stats['mic_frames']} "
                f"last_seq={stats['last_seq']} "
                f"dropped={stats['dropped_count']}"
            )

            _require_result(
                await call_rpc(ws, pending, "mic.unsubscribe", {"topic": _MIC_TOPIC}),
                "mic.unsubscribe",
            )
            print(f"Unsubscribed mic topic: {_MIC_TOPIC}")
        finally:
            reader.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record denoised mic audio through bridge")
    parser.add_argument("--uri", default="ws://localhost:8765", help="Bridge WebSocket URI")
    parser.add_argument("--duration", type=float, default=25.0, help="Recording duration in seconds")
    args = parser.parse_args()
    asyncio.run(main(args.uri, args.duration))
