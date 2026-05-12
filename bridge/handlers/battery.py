from __future__ import annotations

import asyncio
import logging

from emb_task_msgs.msg import BatteryInfo, BatteryState

from bridge.ros2_adapter import Ros2Adapter
from bridge.server import BridgeServer

logger = logging.getLogger(__name__)

_TOPIC_BATTERY_STATE = "/emb/battery_state"


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

    def _on_msg(msg: BatteryState) -> None:
        notification = {
            "jsonrpc": "2.0",
            "method": "battery_state.data",
            "params": _battery_state_to_dict(msg),
        }
        asyncio.run_coroutine_threadsafe(server.broadcast(notification), loop)

    adapter.subscribe_topic(BatteryInfo, _TOPIC_BATTERY_STATE, _on_msg)
    logger.info("Default subscribed to battery topic: %s", _TOPIC_BATTERY_STATE)
