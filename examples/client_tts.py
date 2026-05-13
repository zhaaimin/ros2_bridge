#!/usr/bin/env python3
"""示例客户端 — 调用 voice.speak 播放 TTS 或音频文件。

用法：
    # 先启动桥服务
    source /opt/ros/humble/setup.bash
    PYTHONPATH=. python3 -m bridge.main

    # 文本播报
    python3 examples/client_tts.py --text "你好，我是机器人"

    # 文件播放
    python3 examples/client_tts.py --file-path /tmp/test.wav
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
logger = logging.getLogger("tts_demo")

_REQ_ID = 0


def _next_id() -> int:
    global _REQ_ID
    _REQ_ID += 1
    return _REQ_ID


async def call_rpc(ws, method: str, params: dict[str, Any]) -> dict:
    request = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": method,
        "params": params,
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


async def main(args: argparse.Namespace) -> None:
    params: dict[str, Any]
    if args.file_path:
        params = {
            "type": "file",
            "file_path": args.file_path,
            "is_break": args.is_break,
        }
    else:
        params = {
            "type": "tts",
            "text": args.text,
            "speaker": args.speaker,
            "speed": args.speed,
            "volume": args.volume,
            "pitch": args.pitch,
            "language": args.language,
            "format": args.format,
            "need_save": args.need_save,
            "is_break": args.is_break,
        }

    async with websockets.connect(args.uri) as ws:
        logger.info("Connected to %s", args.uri)
        result = _require_result(
            await call_rpc(ws, "voice.speak", params),
            "voice.speak",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play TTS through bridge voice.speak")
    parser.add_argument("--uri", default="ws://localhost:8765", help="Bridge WebSocket URI")
    parser.add_argument("--text", default="你好，我是机器人", help="TTS text")
    parser.add_argument("--file-path", default="", help="Audio file path for file playback")
    parser.add_argument("--speaker", default="male_01")
    parser.add_argument("--speed", type=int, default=50)
    parser.add_argument("--volume", type=int, default=100)
    parser.add_argument("--pitch", type=int, default=50)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--format", default="wav")
    parser.add_argument("--need-save", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--is-break", action=argparse.BooleanOptionalAction, default=True)
    asyncio.run(main(parser.parse_args()))
