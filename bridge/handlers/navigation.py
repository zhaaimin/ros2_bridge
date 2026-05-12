from __future__ import annotations

from typing import Any

from bridge.dispatcher import register
from bridge.ros2_adapter import Ros2Adapter

# TODO: 替换为实际消息类型，例如：
# from walker_nav_msgs.action import Goto, GotoPose
# from walker_nav_msgs.srv import StopNav, NavStatus, SetMap, Relocate, UpdateSpeed

_ACTION_GOTO = "/walker/navigation/goto"
_ACTION_GOTO_TARGET = "/walker/navigation/goto_target"
_ACTION_GOTO_POSE = "/walker/navigation/goto_pose"
_SRV_STOP = "/walker/navigation/stop"
_SRV_STATUS = "/walker/navigation/status"
_SRV_SET_MAP = "/walker/navigation/set_map"
_SRV_RELOCATE = "/walker/navigation/relocate"
_SRV_UPDATE_SPEED = "/walker/navigation/update_speed"


@register("navigation.goto")
async def goto(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    name: str = params["name"]
    trace_id: str = params.get("trace_id", "")

    # TODO: 这是长时 action，等待完成后返回结果
    # from walker_nav_msgs.action import Goto
    # goal = Goto.Goal(target_name=name, trace_id=trace_id)
    # ros_result = await adapter.send_action_goal(Goto, _ACTION_GOTO, goal)
    # return _nav_result(ros_result)

    raise NotImplementedError("navigation.goto: fill in ROS2 action type and call")


@register("navigation.goto_target")
async def goto_target(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    target_id: str = params["target_id"]
    trace_id: str = params.get("trace_id", "")

    # TODO:
    # from walker_nav_msgs.action import GotoTarget
    # goal = GotoTarget.Goal(target_id=target_id, trace_id=trace_id)
    # ros_result = await adapter.send_action_goal(GotoTarget, _ACTION_GOTO_TARGET, goal)
    # return _nav_result(ros_result)

    raise NotImplementedError("navigation.goto_target: fill in ROS2 action type and call")


@register("navigation.goto_pose")
async def goto_pose(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    x: float = float(params["x"])
    y: float = float(params["y"])
    yaw: float = float(params.get("yaw", 0.0))
    trace_id: str = params.get("trace_id", "")

    # TODO:
    # from walker_nav_msgs.action import GotoPose
    # goal = GotoPose.Goal(x=x, y=y, yaw=yaw, trace_id=trace_id)
    # ros_result = await adapter.send_action_goal(GotoPose, _ACTION_GOTO_POSE, goal)
    # return _nav_result(ros_result)

    raise NotImplementedError("navigation.goto_pose: fill in ROS2 action type and call")


@register("navigation.stop")
async def stop(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    trace_id: str = params.get("trace_id", "")

    # TODO:
    # from walker_nav_msgs.srv import StopNav
    # req = StopNav.Request(trace_id=trace_id)
    # ros_result = await adapter.call_service(StopNav, _SRV_STOP, req)
    # return "accept" if ros_result.success else _fail(ros_result.reason)

    raise NotImplementedError("navigation.stop: fill in ROS2 service type and call")


@register("navigation.status")
async def status(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    # TODO:
    # from walker_nav_msgs.srv import NavStatus
    # req = NavStatus.Request()
    # ros_result = await adapter.call_service(NavStatus, _SRV_STATUS, req)
    # return {"state": ros_result.state, "target": ros_result.target}

    raise NotImplementedError("navigation.status: fill in ROS2 service type and call")


@register("navigation.set_map")
async def set_map(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    map_id: str = params["map_id"]

    # TODO:
    # from walker_nav_msgs.srv import SetMap
    # req = SetMap.Request(map_id=map_id)
    # ros_result = await adapter.call_service(SetMap, _SRV_SET_MAP, req)
    # return "accept" if ros_result.success else _fail(ros_result.message)

    raise NotImplementedError("navigation.set_map: fill in ROS2 service type and call")


@register("navigation.relocate")
async def relocate(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    # TODO:
    # from walker_nav_msgs.srv import Relocate
    # req = Relocate.Request()
    # ros_result = await adapter.call_service(Relocate, _SRV_RELOCATE, req)
    # return "accept"

    raise NotImplementedError("navigation.relocate: fill in ROS2 service type and call")


@register("navigation.update_speed")
async def update_speed(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    speed_level: str = params["speed_level"]

    # TODO:
    # from walker_nav_msgs.srv import UpdateSpeed
    # req = UpdateSpeed.Request(speed_level=speed_level)
    # ros_result = await adapter.call_service(UpdateSpeed, _SRV_UPDATE_SPEED, req)
    # return "accept"

    raise NotImplementedError("navigation.update_speed: fill in ROS2 service type and call")


def _nav_result(ros_result) -> dict:
    return {
        "trace_id": getattr(ros_result, "trace_id", ""),
        "type": getattr(ros_result, "result_type", ""),
        "start_utc_ms": getattr(ros_result, "start_utc_ms", 0),
        "end_utc_ms": getattr(ros_result, "end_utc_ms", 0),
        "succ_result": getattr(ros_result, "succ_result", None),
        "fail_reason": getattr(ros_result, "fail_reason", None),
    }
