from __future__ import annotations

from typing import Any

from bridge.dispatcher import register
from bridge.ros2_adapter import Ros2Adapter

# TODO: 替换为实际消息类型，例如：
# from walker_network_msgs.srv import WifiScan, WifiInfo, WifiSet

_SRV_WIFI_LIST = "/walker/network/wifi/scan"
_SRV_WIFI_INFO = "/walker/network/wifi/info"
_SRV_WIFI_SET = "/walker/network/wifi/set"


@register("network.get_wifi_list")
async def get_wifi_list(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    # TODO:
    # from walker_network_msgs.srv import WifiScan
    # req = WifiScan.Request()
    # ros_result = await adapter.call_service(WifiScan, _SRV_WIFI_LIST, req)
    # return {
    #     "list": [
    #         {
    #             "ssid": ap.ssid,
    #             "signal": ap.signal,
    #             "security": ap.security,
    #             "frequency": ap.frequency,
    #             "connected": ap.connected,
    #         }
    #         for ap in ros_result.access_points
    #     ]
    # }

    raise NotImplementedError("network.get_wifi_list: fill in ROS2 service type and call")


@register("network.get_wifi_info")
async def get_wifi_info(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    # TODO:
    # from walker_network_msgs.srv import WifiInfo
    # req = WifiInfo.Request()
    # ros_result = await adapter.call_service(WifiInfo, _SRV_WIFI_INFO, req)
    # return {
    #     "connected": ros_result.connected,
    #     "ssid": ros_result.ssid or None,
    #     "signal": ros_result.signal if ros_result.connected else None,
    #     "security": ros_result.security or None,
    #     "frequency": ros_result.frequency or None,
    #     "ip": ros_result.ip or None,
    #     "mac": ros_result.mac or None,
    # }

    raise NotImplementedError("network.get_wifi_info: fill in ROS2 service type and call")


@register("network.set_wifi")
async def set_wifi(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    ssid: str = params.get("ssid", "").strip()
    if not ssid:
        raise _wifi_error("ssid_empty")

    password: str = params.get("password") or ""
    hidden: bool = bool(params.get("hidden", False))

    # TODO:
    # from walker_network_msgs.srv import WifiSet
    # req = WifiSet.Request()
    # req.ssid = ssid
    # req.password = password
    # req.hidden = hidden
    # ros_result = await adapter.call_service(WifiSet, _SRV_WIFI_SET, req)
    # if not ros_result.success:
    #     raise _wifi_error(ros_result.reason)
    # return "accept"

    raise NotImplementedError("network.set_wifi: fill in ROS2 service type and call")


def _wifi_error(reason: str) -> RuntimeError:
    return RuntimeError(f'{{"reason": "{reason}"}}')
