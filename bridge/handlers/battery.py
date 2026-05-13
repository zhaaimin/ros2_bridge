from __future__ import annotations

import asyncio
import logging

from emb_task_msgs.msg import BatteryInfo, BatteryState
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from bridge.ros2_adapter import Ros2Adapter
from bridge.server import BridgeServer

logger = logging.getLogger(__name__)

_TOPIC_BATTERY_STATE = "/emb/battery_state"
_BATTERY_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)
_BATTERY_CALLBACK_GROUP = ReentrantCallbackGroup()


def _battery_info_to_dict(msg: BatteryInfo) -> dict:
    return {
        "charge_status": msg.charge_status,
        "voltage": msg.voltage,
        "current": msg.current,
        "temperature": msg.temperature,
        "maxdifvol": msg.maxdifvol,
        "batsoc": msg.batsoc,
        "remainchargetime": msg.remainchargetime,
        "healthstatus": msg.healthstatus,
        "remainuselife": msg.remainuselife,
    }


def _battery_state_to_dict(msg: BatteryState) -> dict:
    return {
        "topic": _TOPIC_BATTERY_STATE,
        "batteries_states": [_battery_info_to_dict(item) for item in msg.batteries_states],
    }


def setup_default_battery_subscription(adapter: Ros2Adapter, server: BridgeServer, loop) -> None:
    """桥启动时默认订阅电池状态，并向全部在线连接广播。"""
    received_count = 0

    def _on_msg(msg: BatteryState) -> None:
        nonlocal received_count
        received_count += 1
        if received_count == 1 or received_count % 100 == 0:
            logger.info(
                "Received battery state from %s: count=%d batteries=%d",
                _TOPIC_BATTERY_STATE,
                received_count,
                len(msg.batteries_states),
            )
        notification = {
            "jsonrpc": "2.0",
            "method": "battery_state.data",
            "params": _battery_state_to_dict(msg),
        }
        asyncio.run_coroutine_threadsafe(server.broadcast(notification), loop)

    adapter.subscribe_topic(
        BatteryState,
        _TOPIC_BATTERY_STATE,
        _on_msg,
        _BATTERY_QOS,
        callback_group=_BATTERY_CALLBACK_GROUP,
    )
    logger.info("Default subscribed to battery topic: %s", _TOPIC_BATTERY_STATE)
