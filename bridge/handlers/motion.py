from __future__ import annotations

import logging
from typing import Any

from mc_task_msgs.srv import GaitModeSwitch

from bridge.dispatcher import register
from bridge.ros2_adapter import Ros2Adapter

logger = logging.getLogger(__name__)

_SRV_MOTION_CTRL = "/mc/leg/motion_ctrl"


@register("motion.gait_mode_switch")
async def gait_mode_switch(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """切换步态模式（遥操控制）。

    对应命令：
        ros2 service call /mc/leg/motion_ctrl mc_task_msgs/srv/GaitModeSwitch "{mode: 200}"

    params:
        mode: int  - 步态模式，例如 200
    """
    mode: int = int(params.get("mode", 200))

    req = GaitModeSwitch.Request()
    req.mode = mode

    ros_result = await adapter.call_service(GaitModeSwitch, _SRV_MOTION_CTRL, req)
    logger.info("GaitModeSwitch mode=%d result=%s", mode, ros_result)

    return {
        "mode": mode,
        "result": str(ros_result),
    }
