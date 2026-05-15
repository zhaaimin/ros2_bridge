from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional, Set, Tuple

from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


class ClientSession:
    """单个 WebSocket 客户端的连接状态和订阅行为。"""

    def __init__(self, websocket: WebSocketServerProtocol, queue_maxsize: int = 64) -> None:
        self.websocket = websocket
        self.topics: Set[str] = set()
        self._cleanups: Dict[str, Callable[[], Any]] = {}
        self._loop = asyncio.get_running_loop()
        self._send_lock = asyncio.Lock()
        self._queue: asyncio.Queue[Tuple[Optional[str], dict]] = asyncio.Queue(
            maxsize=queue_maxsize
        )
        self._sender_task = self._loop.create_task(self._send_loop())

    @property
    def peer(self):
        return self.websocket.remote_address

    def subscribe(self, topic_name: str) -> None:
        self.topics.add(topic_name)

    def unsubscribe(self, topic_name: str) -> None:
        self.topics.discard(topic_name)

    def is_subscribed(self, topic_name: str) -> bool:
        return topic_name in self.topics

    def add_cleanup(self, name: str, cleanup: Callable[[], Any]) -> None:
        self._cleanups[name] = cleanup

    def remove_cleanup(self, name: str) -> None:
        self._cleanups.pop(name, None)

    async def cleanup(self) -> None:
        cleanups = tuple(self._cleanups.items())
        self._cleanups.clear()
        for name, cleanup in cleanups:
            try:
                result = cleanup()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Client cleanup failed: peer=%s name=%s", self.peer, name)

    async def send(self, data: dict) -> None:
        async with self._send_lock:
            await self.websocket.send(json.dumps(data, ensure_ascii=False))

    async def enqueue(self, data: dict, topic_name: Optional[str] = None) -> None:
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait((topic_name, data))
        except Exception:
            logger.debug("Failed to enqueue to %s", self.peer)

    async def _send_loop(self) -> None:
        try:
            while True:
                topic_name, data = await self._queue.get()
                if topic_name is not None and not self.is_subscribed(topic_name):
                    continue
                try:
                    await self.send(data)
                except Exception:
                    logger.debug("Failed to push to %s", self.peer)
        except asyncio.CancelledError:
            pass

    def close(self) -> None:
        if not self._sender_task.done():
            self._sender_task.cancel()
