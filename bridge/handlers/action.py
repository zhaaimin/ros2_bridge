from __future__ import annotations

from typing import Any

from bridge.dispatcher import register
from bridge.ros2_adapter import Ros2Adapter

# TODO: 替换为实际消息类型，例如：
# from walker_action_msgs.srv import ListActions, StopAction
# from walker_action_msgs.action import PlayAction

_SRV_LIST = "/walker/action/list"
_ACTION_PLAY = "/walker/action/play"
_SRV_STOP = "/walker/action/stop"


@register("action.list")
async def list_actions(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    # TODO:
    # from walker_action_msgs.srv import ListActions
    # req = ListActions.Request()
    # ros_result = await adapter.call_service(ListActions, _SRV_LIST, req)
    # return {"list": [{"id": a.id, "name": a.name} for a in ros_result.actions]}

    raise NotImplementedError("action.list: fill in ROS2 service type and call")


@register("action.play")
async def play(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    action_id: str = params["action_id"]
    action_params: dict = params.get("params") or {}
    trace_id: str = params.get("trace_id", "")

    # TODO: 这是长时 action，等待动作完成后返回结果
    # from walker_action_msgs.action import PlayAction
    # goal = PlayAction.Goal()
    # goal.action_id = action_id
    # goal.params = json.dumps(action_params)
    # goal.trace_id = trace_id
    # ros_result = await adapter.send_action_goal(PlayAction, _ACTION_PLAY, goal)
    # return _action_result(ros_result)

    raise NotImplementedError("action.play: fill in ROS2 action type and call")


@register("action.stop")
async def stop(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    trace_id: str = params.get("trace_id", "")

    # TODO:
    # from walker_action_msgs.srv import StopAction
    # req = StopAction.Request(trace_id=trace_id)
    # ros_result = await adapter.call_service(StopAction, _SRV_STOP, req)
    # return "accept" if ros_result.success else _fail(ros_result.reason)

    raise NotImplementedError("action.stop: fill in ROS2 service type and call")


def _action_result(ros_result) -> dict:
    return {
        "trace_id": getattr(ros_result, "trace_id", ""),
        "type": getattr(ros_result, "result_type", ""),
        "start_utc_ms": getattr(ros_result, "start_utc_ms", 0),
        "end_utc_ms": getattr(ros_result, "end_utc_ms", 0),
        "succ_result": getattr(ros_result, "succ_result", None),
        "fail_reason": getattr(ros_result, "fail_reason", None),
    }
