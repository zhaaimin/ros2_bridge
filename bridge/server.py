from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Set

import websockets
from websockets.server import WebSocketServerProtocol

from bridge.client_session import ClientSession
from bridge.dispatcher import dispatch
from bridge.models import JsonRpcRequest, JsonRpcResponse
from bridge.ros2_adapter import Ros2Adapter

logger = logging.getLogger(__name__)


class BridgeServer:
    def __init__(self, adapter: Ros2Adapter) -> None:
        self._adapter = adapter
        self._clients: Dict[WebSocketServerProtocol, ClientSession] = {}
        self._persistent_topics: Set[str] = set()

    async def _handle(self, websocket: WebSocketServerProtocol) -> None:
        session = ClientSession(websocket)
        self._clients[websocket] = session
        logger.info("Client connected: %s", session.peer)
        try:
            async for raw in websocket:
                response = await self._process(raw, websocket)
                await session.send(response.to_dict())
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            session = self._clients.pop(websocket, session)
            session.close()
            topics = set(session.topics)
            for topic in topics:
                if topic not in self._persistent_topics and not self.has_topic_subscribers(topic):
                    self._adapter.unsubscribe_topic(topic)
            logger.info("Client disconnected: %s", session.peer)

    def mark_persistent_topic(self, topic_name: str) -> None:
        """标记由服务维护的常驻 ROS topic，客户端断开时不销毁订阅。"""
        self._persistent_topics.add(topic_name)

    def track_topic(self, websocket: WebSocketServerProtocol, topic_name: str) -> None:
        """记录某个 WebSocket 连接正在订阅的 topic，断连时自动清理。"""
        session = self._clients.get(websocket)
        if session is not None:
            session.subscribe(topic_name)
            logger.info("Client %s subscribed topic: %s", session.peer, topic_name)

    def untrack_topic(self, websocket: WebSocketServerProtocol, topic_name: str) -> None:
        """移除跟踪。"""
        session = self._clients.get(websocket)
        if session is not None:
            session.unsubscribe(topic_name)
            logger.info("Client %s unsubscribed topic: %s", session.peer, topic_name)

    def has_connections(self) -> bool:
        """是否存在在线 WebSocket 连接。"""
        return bool(self._clients)

    def has_topic_subscribers(self, topic_name: str) -> bool:
        """是否存在订阅指定 topic 的在线 WebSocket 连接。"""
        return any(session.is_subscribed(topic_name) for session in self._clients.values())

    async def push_to(self, websocket: WebSocketServerProtocol, data: dict) -> None:
        """向指定 WebSocket 连接推送 JSON-RPC notification。"""
        session = self._clients.get(websocket)
        if session is not None:
            await session.enqueue(data)

    async def broadcast(self, data: dict) -> None:
        """向所有在线 WebSocket 连接广播 JSON-RPC notification。"""
        if not self._clients:
            return
        await asyncio.gather(
            *(session.enqueue(data) for session in tuple(self._clients.values())),
            return_exceptions=True,
        )

    async def broadcast_topic(self, topic_name: str, data: dict) -> None:
        """向订阅指定 topic 的 WebSocket 连接广播 JSON-RPC notification。"""
        targets = [
            session
            for session in tuple(self._clients.values())
            if session.is_subscribed(topic_name)
        ]
        if not targets:
            return
        await asyncio.gather(
            *(session.enqueue(data, topic_name=topic_name) for session in targets),
            return_exceptions=True,
        )

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
