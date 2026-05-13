from __future__ import annotations

import asyncio
import logging
from typing import Any

from std_msgs.msg import Int16MultiArray

from bridge.audio_recorder import WavRecorder
from bridge.dispatcher import register
from bridge.ros2_adapter import Ros2Adapter
from bridge.server import BridgeServer

logger = logging.getLogger(__name__)

# TODO: 替换为实际 ROS2 service/action 消息类型，例如：
# from walker_voice_msgs.srv import Speak, StopSpeak, SetVolume, SetSystemVolume

_SRV_SPEAK = "/walker/voice/speak"
_SRV_STOP = "/walker/voice/stop"
_SRV_SET_VOLUME = "/walker/voice/set_volume"
_SRV_SET_SYSTEM_VOLUME = "/walker/voice/set_system_volume"

_TOPIC_MIC_SOURCE = "/sys/speech/mic_source"
_TOPIC_MIC_DENOISE = "/sys/speech/mic_denoise"

_VALID_MIC_TOPICS = {_TOPIC_MIC_SOURCE, _TOPIC_MIC_DENOISE}
_DEFAULT_MIC_TOPIC = _TOPIC_MIC_DENOISE
_MIC_SAMPLE_RATE = 16000
_MIC_CHANNELS = {
    _TOPIC_MIC_SOURCE: 8,
    _TOPIC_MIC_DENOISE: 1,
}
_AUTO_RECORD_DELAY_SEC = 10
_AUTO_RECORD_DURATION_SEC = 25
_RECORDER = WavRecorder()


@register("voice.speak")
async def speak(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    text: str = params["text"]
    speed: int = params.get("speed", 50)
    volume: int = params.get("volume", 60)

    # TODO: 替换下方注释为实际 ROS2 调用：
    # from walker_voice_msgs.srv import Speak
    # req = Speak.Request()
    # req.text = text
    # req.speed = speed
    # req.volume = volume
    # ros_result = await adapter.call_service(Speak, _SRV_SPEAK, req)
    # return "accept" if ros_result.success else _fail(ros_result.message)

    raise NotImplementedError("voice.speak: fill in ROS2 service type and call")


@register("voice.stop")
async def stop(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    trace_id: str = params.get("trace_id", "")

    # TODO:
    # from walker_voice_msgs.srv import StopSpeak
    # req = StopSpeak.Request()
    # req.trace_id = trace_id
    # ros_result = await adapter.call_service(StopSpeak, _SRV_STOP, req)
    # return "accept" if ros_result.success else _fail(ros_result.message)

    raise NotImplementedError("voice.stop: fill in ROS2 service type and call")


@register("voice.set_volume")
async def set_volume(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    volume: int = int(params["volume"])
    if not 0 <= volume <= 100:
        raise ValueError("volume must be in range 0~100")

    # TODO:
    # from walker_voice_msgs.srv import SetVolume
    # req = SetVolume.Request(volume=volume)
    # ros_result = await adapter.call_service(SetVolume, _SRV_SET_VOLUME, req)
    # return {"volume": volume}

    raise NotImplementedError("voice.set_volume: fill in ROS2 service type and call")


@register("voice.set_system_volume")
async def set_system_volume(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    volume: int = int(params["volume"])
    if not 0 <= volume <= 100:
        raise ValueError("volume must be in range 0~100")

    # TODO:
    # from walker_voice_msgs.srv import SetSystemVolume
    # req = SetSystemVolume.Request(volume=volume)
    # ros_result = await adapter.call_service(SetSystemVolume, _SRV_SET_SYSTEM_VOLUME, req)
    # return {"volume": volume}

    raise NotImplementedError("voice.set_system_volume: fill in ROS2 service type and call")


# ---------------------------------------------------------------------------
# 麦克风数据订阅
# ---------------------------------------------------------------------------

def _int16_multiarray_to_dict(msg: Int16MultiArray) -> dict:
    """将 std_msgs/Int16MultiArray 转为可 JSON 序列化的 dict。"""
    layout = msg.layout
    dims = [
        {"label": d.label, "size": d.size, "stride": d.stride}
        for d in layout.dim
    ]
    return {
        "layout": {
            "dim": dims,
            "data_offset": layout.data_offset,
        },
        "data": list(msg.data),
    }


def setup_default_mic_subscription(adapter: Ros2Adapter, server: BridgeServer, loop) -> None:
    """桥启动时默认订阅降噪麦克风数据，并向全部在线连接广播。"""
    received_count = 0
    auto_record_scheduled = False

    async def _auto_record_once() -> None:
        await asyncio.sleep(_AUTO_RECORD_DELAY_SEC)
        try:
            started = _RECORDER.start(
                topic=_DEFAULT_MIC_TOPIC,
                channels=_MIC_CHANNELS[_DEFAULT_MIC_TOPIC],
                sample_rate=_MIC_SAMPLE_RATE,
            )
            logger.info(
                "Auto mic recording started: path=%s duration=%ss",
                started["path"],
                _AUTO_RECORD_DURATION_SEC,
            )
        except Exception as exc:
            logger.warning("Auto mic recording start skipped: %s", exc)
            return

        await asyncio.sleep(_AUTO_RECORD_DURATION_SEC)
        try:
            stopped = _RECORDER.stop()
            logger.info("Auto mic recording stopped: path=%s", stopped["path"])
        except Exception as exc:
            logger.warning("Auto mic recording stop skipped: %s", exc)

    def _on_msg(msg: Int16MultiArray) -> None:
        nonlocal auto_record_scheduled, received_count
        received_count += 1
        if received_count == 1 or received_count % 100 == 0:
            logger.info(
                "Received mic data from %s: count=%d samples=%d",
                _DEFAULT_MIC_TOPIC,
                received_count,
                len(msg.data),
            )
        if not auto_record_scheduled:
            auto_record_scheduled = True
            asyncio.run_coroutine_threadsafe(_auto_record_once(), loop)
        _RECORDER.write_msg(_DEFAULT_MIC_TOPIC, msg)
        if not server.has_connections():
            return
        notification = {
            "jsonrpc": "2.0",
            "method": "mic.data",
            "params": {
                "topic": _DEFAULT_MIC_TOPIC,
                **_int16_multiarray_to_dict(msg),
            },
        }
        asyncio.run_coroutine_threadsafe(server.broadcast(notification), loop)

    adapter.subscribe_topic(Int16MultiArray, _DEFAULT_MIC_TOPIC, _on_msg)
    logger.info("Default subscribed to mic topic: %s", _DEFAULT_MIC_TOPIC)


@register("mic.record_start")
async def mic_record_start(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """开始保存默认降噪麦克风数据为 WAV 文件。"""
    topic: str = params.get("topic", _DEFAULT_MIC_TOPIC)
    if topic != _DEFAULT_MIC_TOPIC:
        raise ValueError(f"recording topic must be {_DEFAULT_MIC_TOPIC!r}")
    return _RECORDER.start(
        topic=topic,
        channels=_MIC_CHANNELS[topic],
        sample_rate=int(params.get("sample_rate", _MIC_SAMPLE_RATE)),
    )


@register("mic.record_stop")
async def mic_record_stop(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """停止保存麦克风 WAV 文件。"""
    return _RECORDER.stop()


@register("mic.record_status")
async def mic_record_status(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """获取当前麦克风录音状态。"""
    return _RECORDER.status()


@register("mic.subscribe")
async def mic_subscribe(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """订阅麦克风话题，持续向当前 WebSocket 连接推送音频数据。

    params:
        topic: str  - 话题名称，可选值:
            "/sys/speech/mic_source"  — 原始 8 通道 16KHz
            "/sys/speech/mic_denoise" — 降噪后 1 通道 16KHz
    """
    server = kwargs.get("server")
    websocket = kwargs.get("websocket")
    if server is None or websocket is None:
        raise RuntimeError("mic.subscribe requires WebSocket context")

    topic: str = params.get("topic", _TOPIC_MIC_SOURCE)
    if topic not in _VALID_MIC_TOPICS:
        raise ValueError(
            f"Invalid topic: {topic!r}, must be one of {sorted(_VALID_MIC_TOPICS)}"
        )

    loop = asyncio.get_running_loop()

    def _on_msg(msg: Int16MultiArray) -> None:
        notification = {
            "jsonrpc": "2.0",
            "method": "mic.data",
            "params": {
                "topic": topic,
                **_int16_multiarray_to_dict(msg),
            },
        }
        asyncio.run_coroutine_threadsafe(server.push_to(websocket, notification), loop)

    adapter.subscribe_topic(Int16MultiArray, topic, _on_msg)
    server.track_topic(websocket, topic)
    logger.info("Client subscribed to mic topic: %s", topic)
    return {"status": "subscribed", "topic": topic}


@register("mic.unsubscribe")
async def mic_unsubscribe(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """取消订阅麦克风话题。

    params:
        topic: str  - 话题名称
    """
    server = kwargs.get("server")
    websocket = kwargs.get("websocket")
    if server is None or websocket is None:
        raise RuntimeError("mic.unsubscribe requires WebSocket context")

    topic: str = params.get("topic", _TOPIC_MIC_SOURCE)
    if topic not in _VALID_MIC_TOPICS:
        raise ValueError(
            f"Invalid topic: {topic!r}, must be one of {sorted(_VALID_MIC_TOPICS)}"
        )

    adapter.unsubscribe_topic(topic)
    server.untrack_topic(websocket, topic)
    logger.info("Client unsubscribed from mic topic: %s", topic)
    return {"status": "unsubscribed", "topic": topic}


def _fail(message: str) -> dict:
    raise RuntimeError(message)
