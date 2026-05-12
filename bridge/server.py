from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Set

import websockets
from websockets.server import WebSocketServerProtocol

from bridge.dispatcher import dispatch
from bridge.models import JsonRpcRequest, JsonRpcResponse
from bridge.ros2_adapter import Ros2Adapter

logger = logging.getLogger(__name__)


class BridgeServer:
    def __init__(self, adapter: Ros2Adapter) -> None:
        self._adapter = adapter
        self._connections: Set[WebSocketServerProtocol] = set()
        self._ws_topics: Dict[WebSocketServerProtocol, Set[str]] = {}

    async def _handle(self, websocket: WebSocketServerProtocol) -> None:
        peer = websocket.remote_address
        self._connections.add(websocket)
        self._ws_topics[websocket] = set()
        logger.info("Client connected: %s", peer)
        try:
            async for raw in websocket:
                response = await self._process(raw, websocket)
                await websocket.send(json.dumps(response.to_dict(), ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            topics = self._ws_topics.pop(websocket, set())
            for topic in topics:
                self._adapter.unsubscribe_topic(topic)
            self._connections.discard(websocket)
            logger.info("Client disconnected: %s", peer)

    def track_topic(self, websocket: WebSocketServerProtocol, topic_name: str) -> None:
        """记录某个 WebSocket 连接正在订阅的 topic，断连时自动清理。"""
        if websocket in self._ws_topics:
            self._ws_topics[websocket].add(topic_name)

    def untrack_topic(self, websocket: WebSocketServerProtocol, topic_name: str) -> None:
        """移除跟踪。"""
        if websocket in self._ws_topics:
            self._ws_topics[websocket].discard(topic_name)

    async def push_to(self, websocket: WebSocketServerProtocol, data: dict) -> None:
        """向指定 WebSocket 连接推送 JSON-RPC notification。"""
        try:
            await websocket.send(json.dumps(data, ensure_ascii=False))
        except Exception:
            logger.debug("Failed to push to %s", websocket.remote_address)

    async def _process(self, raw: str, websocket: WebSocketServerProtocol) -> JsonRpcResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return JsonRpcResponse(
                id=None,
                error={"code": -32700, "message": f"Parse error: {exc}"},
            )

        if not isinstance(data, dict) or "method" not in data:
            return JsonRpcResponse(
                id=data.get("id") if isinstance(data, dict) else None,
                error={"code": -32600, "message": "Invalid Request"},
            )

        req = JsonRpcRequest.from_dict(data)
        logger.debug("→ %s id=%s", req.method, req.id)
        resp = await dispatch(req, self._adapter, server=self, websocket=websocket)
        logger.debug("← %s id=%s ok=%s", req.method, resp.id, resp.error is None)
        return resp

    async def serve(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        import asyncio
        logger.info("Bridge listening on ws://%s:%d", host, port)
        async with websockets.serve(self._handle, host, port):
            await asyncio.Future()
