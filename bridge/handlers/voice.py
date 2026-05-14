from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from typing import Any, Deque, Tuple

from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Int16MultiArray
from sys_task_msgs.action import Tts

from bridge.audio_recorder import WavRecorder
from bridge.dispatcher import register
from bridge.ros2_adapter import Ros2Adapter
from bridge.server import BridgeServer

logger = logging.getLogger(__name__)

_ACTION_TTS = "/sys/speech/tts"
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
_MIC_CALLBACK_GROUP = MutuallyExclusiveCallbackGroup()
_MIC_QUEUE_MAXLEN = 10
_MIC_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=_MIC_QUEUE_MAXLEN,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)
_RECORDER = WavRecorder()


def _node_state_to_dict(msg) -> dict:
    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None)
    return {
        "header": {
            "stamp": {
                "sec": getattr(stamp, "sec", 0),
                "nanosec": getattr(stamp, "nanosec", 0),
            },
            "frame_id": getattr(header, "frame_id", ""),
        },
        "state": getattr(msg, "state", 0),
        "desc": getattr(msg, "desc", ""),
        "msg_type": getattr(msg, "msg_type", ""),
    }


@register("voice.speak")
async def speak(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """通过 /sys/speech/tts action 播放 TTS 文本或音频文件。"""
    goal = Tts.Goal()

    play_type = params.get("type", "tts")
    if isinstance(play_type, str):
        play_type = play_type.lower()
        if play_type == "tts":
            goal.type = Tts.Goal.TTS
        elif play_type == "file":
            goal.type = Tts.Goal.FILE
        else:
            raise ValueError("params.type must be 'tts' or 'file'")
    else:
        goal.type = int(play_type)

    goal.is_break = bool(params.get("is_break", True))

    if goal.type == Tts.Goal.FILE:
        goal.file_path = params["file_path"]
    else:
        goal.text = params["text"]

    goal.speaker = params.get("speaker", "male_01")
    goal.speed = int(params.get("speed", 50))
    goal.volume = int(params.get("volume", 100))
    goal.pitch = int(params.get("pitch", 50))
    goal.language = params.get("language", "zh")
    goal.format = params.get("format", "wav")
    goal.need_save = bool(params.get("need_save", True))

    result = await adapter.send_action_goal(Tts, _ACTION_TTS, goal)
    logger.info("TTS action finished: %s", result.result)
    return {
        "action": _ACTION_TTS,
        "result": _node_state_to_dict(result.result),
    }


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
    next_seq = 0
    dropped_count = 0
    mic_queue: Deque[Tuple[int, Int16MultiArray, int]] = deque(maxlen=_MIC_QUEUE_MAXLEN)
    queue_lock = threading.Lock()

    async def _push_queued_mic_data() -> None:
        while True:
            await asyncio.sleep(0)
            if not server.has_topic_subscribers(_DEFAULT_MIC_TOPIC):
                with queue_lock:
                    mic_queue.clear()
                await asyncio.sleep(0.02)
                continue
            with queue_lock:
                if not mic_queue:
                    item = None
                else:
                    item = mic_queue.popleft()
            if item is None:
                await asyncio.sleep(0.005)
                continue
            seq, msg, dropped_before = item
            with queue_lock:
                queued_count = len(mic_queue)
            if seq == 0 or seq % 100 == 0:
                logger.info(
                    "Queueing mic push: seq=%d queued=%d dropped=%d",
                    seq,
                    queued_count,
                    dropped_before,
                )
            notification = {
                "jsonrpc": "2.0",
                "method": "mic.data",
                "params": {
                    "topic": _DEFAULT_MIC_TOPIC,
                    "seq": seq,
                    "dropped_count": dropped_before,
                    "queued_count": queued_count,
                    **_int16_multiarray_to_dict(msg),
                },
            }
            try:
                await server.broadcast_topic(_DEFAULT_MIC_TOPIC, notification)
            except Exception:
                logger.exception("Failed to broadcast mic data")

    asyncio.run_coroutine_threadsafe(_push_queued_mic_data(), loop)

    def _on_msg(msg: Int16MultiArray) -> None:
        nonlocal dropped_count, next_seq, received_count
        received_count += 1
        if received_count == 1 or received_count % 100 == 0:
            logger.info(
                "Received mic data from %s: count=%d samples=%d",
                _DEFAULT_MIC_TOPIC,
                received_count,
                len(msg.data),
            )

        _RECORDER.write_msg(_DEFAULT_MIC_TOPIC, msg)
        with queue_lock:
            if len(mic_queue) == mic_queue.maxlen:
                dropped_count += 1
            mic_queue.append((next_seq, msg, dropped_count))
            next_seq += 1

    adapter.subscribe_topic(
        Int16MultiArray,
        _DEFAULT_MIC_TOPIC,
        _on_msg,
        _MIC_QOS,
        callback_group=_MIC_CALLBACK_GROUP,
    )
    server.mark_persistent_topic(_DEFAULT_MIC_TOPIC)
    logger.info("Default subscribed to mic topic: %s", _DEFAULT_MIC_TOPIC)


@register("mic.record_start")
async def mic_record_start(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """开始保存默认降噪麦克风数据为 WAV 文件。"""
    topic: str = params.get("topic", _DEFAULT_MIC_TOPIC)
    if topic != _DEFAULT_MIC_TOPIC:
        raise ValueError(f"recording topic must be {_DEFAULT_MIC_TOPIC!r}")
    status = _RECORDER.start(
        topic=topic,
        channels=_MIC_CHANNELS[topic],
        sample_rate=int(params.get("sample_rate", _MIC_SAMPLE_RATE)),
    )
    logger.info("Manual mic recording started: path=%s", status["path"])
    return status


@register("mic.record_stop")
async def mic_record_stop(params: dict, adapter: Ros2Adapter, **kwargs: Any) -> Any:
    """停止保存麦克风 WAV 文件。"""
    status = _RECORDER.stop()
    logger.info(
        "Manual mic recording stopped: path=%s duration=%.3fs frames=%d",
        status["path"],
        status["duration_sec"],
        status["frames_written"],
    )
    return status


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
    pushed_count = 0

    def _on_msg(msg: Int16MultiArray) -> None:
        nonlocal pushed_count
        if not server.has_topic_subscribers(topic):
            return
        pushed_count += 1
        notification = {
            "jsonrpc": "2.0",
            "method": "mic.data",
            "params": {
                "topic": topic,
                **_int16_multiarray_to_dict(msg),
            },
        }
        if pushed_count == 1 or pushed_count % 100 == 0:
            logger.info("Pushing mic topic %s: count=%d", topic, pushed_count)
        asyncio.run_coroutine_threadsafe(server.broadcast_topic(topic, notification), loop)

    if topic != _DEFAULT_MIC_TOPIC:
        adapter.subscribe_topic(Int16MultiArray, topic, _on_msg, _MIC_QOS)
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

    server.untrack_topic(websocket, topic)
    if topic != _DEFAULT_MIC_TOPIC and not server.has_topic_subscribers(topic):
        adapter.unsubscribe_topic(topic)
    logger.info("Client unsubscribed from mic topic: %s", topic)
    return {"status": "unsubscribed", "topic": topic}


def _fail(message: str) -> dict:
    raise RuntimeError(message)
