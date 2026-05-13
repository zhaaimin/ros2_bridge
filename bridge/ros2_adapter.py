from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Type

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node


class Ros2Adapter:
    """asyncio-safe ROS2 service / action client wrapper.

    启动方式::

        loop = asyncio.get_running_loop()
        adapter = Ros2Adapter()
        adapter.start_in_thread(loop)
        adapter.wait_ready()
    """

    def __init__(self) -> None:
        self.node: Node = None
        self._executor: MultiThreadedExecutor = None
        self._loop = None
        self._ready = threading.Event()
        self._call_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ros2_call")
        self._subscriptions: Dict[str, Any] = {}

    def start_in_thread(self, loop) -> threading.Thread:
        """在后台线程中启动 rclpy spin，不阻塞 asyncio 事件循环。"""
        self._loop = loop

        def _spin() -> None:
            rclpy.init()
            self.node = rclpy.create_node("bridge_node")
            self._executor = MultiThreadedExecutor()
            self._executor.add_node(self.node)
            self._ready.set()
            try:
                self._executor.spin()
            finally:
                rclpy.shutdown()

        t = threading.Thread(target=_spin, name="rclpy_spin", daemon=True)
        t.start()
        return t

    def wait_ready(self, timeout: float = 10.0) -> bool:
        return self._ready.wait(timeout=timeout)

    async def call_service(self, srv_type: Type, srv_name: str, request: Any) -> Any:
        """将 ROS2 service 调用包装为 awaitable。"""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._call_pool,
            self._call_service_sync,
            srv_type,
            srv_name,
            request,
        )

    def _call_service_sync(self, srv_type: Type, srv_name: str, request: Any) -> Any:
        cli = self.node.create_client(srv_type, srv_name)
        if not cli.wait_for_service(timeout_sec=5.0):
            raise TimeoutError(f"ROS2 service {srv_name!r} not available")

        done = threading.Event()
        container: dict = {}

        def _on_done(future) -> None:
            try:
                container["result"] = future.result()
            except Exception as exc:
                container["error"] = exc
            done.set()

        ros_future = cli.call_async(request)
        ros_future.add_done_callback(_on_done)

        if not done.wait(timeout=10.0):
            raise TimeoutError(f"ROS2 service {srv_name!r} response timed out")
        if "error" in container:
            raise container["error"]
        return container["result"]

    async def send_action_goal(self, action_type: Type, action_name: str, goal: Any) -> Any:
        """将 ROS2 action goal 发送包装为 awaitable，等待 result 返回。"""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._call_pool,
            self._send_action_goal_sync,
            action_type,
            action_name,
            goal,
        )

    def _send_action_goal_sync(self, action_type: Type, action_name: str, goal: Any) -> Any:
        from rclpy.action import ActionClient as RosActionClient

        cli = RosActionClient(self.node, action_type, action_name)
        if not cli.wait_for_server(timeout_sec=5.0):
            raise TimeoutError(f"ROS2 action server {action_name!r} not available")

        done = threading.Event()
        container: dict = {}

        def _on_goal_response(goal_handle_future) -> None:
            goal_handle = goal_handle_future.result()
            if not goal_handle.accepted:
                container["error"] = RuntimeError(f"Goal rejected by action server {action_name!r}")
                done.set()
                return
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(_on_result)

        def _on_result(result_future) -> None:
            try:
                container["result"] = result_future.result().result
            except Exception as exc:
                container["error"] = exc
            done.set()

        send_future = cli.send_goal_async(goal)
        send_future.add_done_callback(_on_goal_response)

        if not done.wait(timeout=60.0):
            raise TimeoutError(f"ROS2 action {action_name!r} timed out")
        if "error" in container:
            raise container["error"]
        return container["result"]

    def subscribe_topic(
        self,
        msg_type: Type,
        topic_name: str,
        callback: Callable[[Any], None],
        qos_profile: Any = 10,
    ) -> None:
        """订阅 ROS2 topic，每收到一条消息就调用 *callback*。

        callback 在 rclpy spin 线程中被调用，如需转发到 asyncio
        请在 callback 中使用 loop.call_soon_threadsafe。
        """
        if topic_name in self._subscriptions:
            return
        sub = self.node.create_subscription(msg_type, topic_name, callback, qos_profile)
        self._subscriptions[topic_name] = sub

    def unsubscribe_topic(self, topic_name: str) -> None:
        """取消订阅 ROS2 topic。"""
        sub = self._subscriptions.pop(topic_name, None)
        if sub is not None:
            self.node.destroy_subscription(sub)
