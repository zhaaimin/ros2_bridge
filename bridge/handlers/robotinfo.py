from __future__ import annotations

from typing import Any

from bridge.dispatcher import register
from bridge.ros2_adapter import Ros2Adapter

# TODO: 替换为实际消息类型，例如：
# from walker_info_msgs.srv import GetStatus, GetInfo

_SRV_GET_STATUS = "/walker/robot/get_status"
_SRV_GET_INFO = "/walker/robot/get_info"


@register("robotinfo.get_status")
async def get_status(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    status_ids: list = params.get("status_ids") or params.get("list") or []
    if not status_ids:
        raise ValueError("params.status_ids must be a non-empty list")

    # TODO:
    # from walker_info_msgs.srv import GetStatus
    # req = GetStatus.Request()
    # req.status_ids = status_ids
    # ros_result = await adapter.call_service(GetStatus, _SRV_GET_STATUS, req)
    # return {item.id: item.value for item in ros_result.items}

    raise NotImplementedError("robotinfo.get_status: fill in ROS2 service type and call")


@register("robotinfo.get_info")
async def get_info(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    # TODO:
    # from walker_info_msgs.srv import GetInfo
    # req = GetInfo.Request()
    # ros_result = await adapter.call_service(GetInfo, _SRV_GET_INFO, req)
    # return {
    #     "model": ros_result.model,
    #     "sn": ros_result.sn,
    #     "version": ros_result.version,
    # }

    raise NotImplementedError("robotinfo.get_info: fill in ROS2 service type and call")
