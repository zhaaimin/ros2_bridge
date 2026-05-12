#!/usr/bin/env python3
"""Mock Bridge Server — 不依赖 ROS2，纯 WebSocket 模拟。

用于本地开发调试，模拟 bridge 收到 JSON-RPC 请求后的响应行为。

用法：
    python3 examples/mock_bridge_server.py [--port 8765]
"""

import asyncio
import json
import logging
import argparse

import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mock_bridge")

# ---------------------------------------------------------------------------
# 模拟 handler：method -> response builder
# ---------------------------------------------------------------------------

def _mock_gait_mode_switch(params: dict) -> dict:
    """模拟 /mc/leg/motion_ctrl GaitModeSwitch 服务的返回。"""
    mode = params.get("mode", 200)
    logger.info("  [MOCK ROS2] GaitModeSwitch called with mode=%s", mode)
    # 模拟 ROS2 service 返回
    return {
        "mode": mode,
        "result": f"mc_task_msgs.srv.GaitModeSwitch_Response(result=0, message='success')",
    }


def _mock_mic_subscribe(params: dict) -> dict:
    topic = params.get("topic", "/sys/speech/mic_source")
    logger.info("  [MOCK ROS2] mic.subscribe topic=%s", topic)
    return {"status": "subscribed", "topic": topic}


def _mock_mic_unsubscribe(params: dict) -> dict:
    topic = params.get("topic", "/sys/speech/mic_source")
    logger.info("  [MOCK ROS2] mic.unsubscribe topic=%s", topic)
    return {"status": "unsubscribed", "topic": topic}


MOCK_HANDLERS = {
    "motion.gait_mode_switch": _mock_gait_mode_switch,
    "mic.subscribe": _mock_mic_subscribe,
    "mic.unsubscribe": _mock_mic_unsubscribe,
}

# ---------------------------------------------------------------------------
# WebSocket 服务
# ---------------------------------------------------------------------------

async def _handle(websocket: WebSocketServerProtocol) -> None:
    peer = websocket.remote_address
    logger.info("Client connected: %s", peer)

    try:
        async for raw in websocket:
            logger.info("← recv: %s", raw)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
                await websocket.send(json.dumps(resp, ensure_ascii=False))
                continue

            req_id = data.get("id")
            method = data.get("method", "")
            params = data.get("params") or {}

            handler = MOCK_HANDLERS.get(method)
            if handler is None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            else:
                try:
                    result = handler(params)
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
                except Exception as exc:
                    resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}}

            out = json.dumps(resp, ensure_ascii=False)
            logger.info("→ send: %s", out)
            await websocket.send(out)

            # 如果是 mic.subscribe，额外模拟推送几帧数据
            if method == "mic.subscribe":
                await _simulate_mic_push(websocket, params.get("topic", "/sys/speech/mic_source"))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        logger.info("Client disconnected: %s", peer)


async def _simulate_mic_push(websocket: WebSocketServerProtocol, topic: str) -> None:
    """订阅后模拟推送 3 帧麦克风数据。"""
    channels = 8 if topic == "/sys/speech/mic_source" else 1
    for i in range(3):
        await asyncio.sleep(0.5)
        notification = {
            "jsonrpc": "2.0",
            "method": "mic.data",
            "params": {
                "topic": topic,
                "layout": {
                    "dim": [
                        {"label": "channels", "size": channels, "stride": channels * 160},
                        {"label": "samples", "size": 160, "stride": 160},
                    ],
                    "data_offset": 0,
                },
                "data": [i * 100 + j for j in range(channels * 160)],
            },
        }
        out = json.dumps(notification, ensure_ascii=False)
        logger.info("→ push mic.data frame %d (%d samples)", i, channels * 160)
        try:
            await websocket.send(out)
        except Exception:
            break


async def main(port: int) -> None:
    logger.info("Mock Bridge Server listening on ws://0.0.0.0:%d", port)
    async with websockets.serve(_handle, "0.0.0.0", port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Bridge Server")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    asyncio.run(main(args.port))
