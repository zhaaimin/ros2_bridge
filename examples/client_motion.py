#!/usr/bin/env python3
"""示例客户端 — 调用 motion.gait_mode_switch 和 mic.subscribe。

用法：
    # 先启动 mock 服务端
    python3 examples/mock_bridge_server.py

    # 再运行本客户端
    python3 examples/client_motion.py [--uri ws://localhost:8765]
"""

import asyncio
import argparse
import json
import logging

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("example_client")

_REQ_ID = 0


def _next_id() -> int:
    global _REQ_ID
    _REQ_ID += 1
    return _REQ_ID


def _build_request(method: str, params: dict) -> str:
    req = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": method,
        "params": params,
    }
    return json.dumps(req, ensure_ascii=False)


async def call_rpc(ws, method: str, params: dict) -> dict:
    """发送 JSON-RPC 请求并等待响应。"""
    raw = _build_request(method, params)
    logger.info("→ %s", raw)
    await ws.send(raw)
    resp_raw = await ws.recv()
    resp = json.loads(resp_raw)
    logger.info("← %s", json.dumps(resp, ensure_ascii=False))
    return resp


async def main(uri: str) -> None:
    async with websockets.connect(uri) as ws:
        logger.info("已连接到 %s", uri)

        # --------------------------------------------------
        # 1. 调用遥操指令：motion.gait_mode_switch
        # --------------------------------------------------
        print("\n" + "=" * 60)
        print("  [1] 调用 motion.gait_mode_switch (mode=200)")
        print("=" * 60)
        resp = await call_rpc(ws, "motion.gait_mode_switch", {"mode": 200})
        if "result" in resp:
            print(f"  ✅ 成功: {json.dumps(resp['result'], ensure_ascii=False, indent=2)}")
        else:
            print(f"  ❌ 失败: {resp.get('error')}")

        # --------------------------------------------------
        # 2. 调用 motion.gait_mode_switch 用不同 mode
        # --------------------------------------------------
        print("\n" + "=" * 60)
        print("  [2] 调用 motion.gait_mode_switch (mode=100)")
        print("=" * 60)
        resp = await call_rpc(ws, "motion.gait_mode_switch", {"mode": 100})
        if "result" in resp:
            print(f"  ✅ 成功: {json.dumps(resp['result'], ensure_ascii=False, indent=2)}")
        else:
            print(f"  ❌ 失败: {resp.get('error')}")

        # --------------------------------------------------
        # 3. 订阅麦克风原始数据
        # --------------------------------------------------
        print("\n" + "=" * 60)
        print("  [3] 订阅 mic_source (8通道 16KHz)")
        print("=" * 60)
        resp = await call_rpc(ws, "mic.subscribe", {"topic": "/sys/speech/mic_source"})
        if "result" in resp:
            print(f"  ✅ 订阅成功: {resp['result']}")
        else:
            print(f"  ❌ 订阅失败: {resp.get('error')}")

        # 接收模拟推送的麦克风数据帧
        print("\n  等待接收麦克风推送数据...")
        for _ in range(3):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg = json.loads(raw)
                if msg.get("method") == "mic.data":
                    p = msg["params"]
                    data_len = len(p.get("data", []))
                    dims = p.get("layout", {}).get("dim", [])
                    print(f"  🎤 收到 mic.data: topic={p['topic']}, "
                          f"dims={dims}, data_length={data_len}")
                else:
                    print(f"  📩 收到: {json.dumps(msg, ensure_ascii=False)}")
            except asyncio.TimeoutError:
                print("  ⏰ 等待超时，无更多数据")
                break

        # --------------------------------------------------
        # 4. 取消订阅
        # --------------------------------------------------
        print("\n" + "=" * 60)
        print("  [4] 取消订阅 mic_source")
        print("=" * 60)
        resp = await call_rpc(ws, "mic.unsubscribe", {"topic": "/sys/speech/mic_source"})
        if "result" in resp:
            print(f"  ✅ 取消成功: {resp['result']}")
        else:
            print(f"  ❌ 取消失败: {resp.get('error')}")

        # --------------------------------------------------
        # 5. 调用不存在的方法（测试错误处理）
        # --------------------------------------------------
        print("\n" + "=" * 60)
        print("  [5] 调用不存在的方法 (预期失败)")
        print("=" * 60)
        resp = await call_rpc(ws, "nonexistent.method", {})
        if "error" in resp:
            print(f"  ✅ 预期错误: {resp['error']}")
        else:
            print(f"  ❓ 意外成功: {resp}")

        print("\n" + "=" * 60)
        print("  所有测试完成！")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Example JSON-RPC Client")
    parser.add_argument("--uri", default="ws://localhost:8765", help="Bridge WebSocket URI")
    args = parser.parse_args()
    asyncio.run(main(args.uri))
