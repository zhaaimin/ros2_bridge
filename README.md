# Bridge — WebSocket JSON-RPC → ROS2 桥接服务

将上层 JSON-RPC 2.0 over WebSocket 指令转发给机器人底层 ROS2 服务。

## 目录结构

```
bridge/
  main.py              # 入口
  server.py            # WebSocket 服务器 + JSON-RPC 解析
  dispatcher.py        # method → handler 路由
  ros2_adapter.py      # asyncio ↔ rclpy 异步桥接
  models.py            # JsonRpcRequest / JsonRpcResponse
  handlers/
    voice.py           # voice.*
    navigation.py      # navigation.*
    action.py          # action.*
    robotinfo.py       # robotinfo.*
    network.py         # network.*
  requirements.txt
  install.sh
```

## 依赖

- ROS2（Humble / Iron / …），需提前安装并 source
- Python 3.8+
- `websockets>=12.0`（通过 pip 安装）

## 快速启动

```bash
# 1. source ROS2 环境
source /opt/ros/humble/setup.bash

# 2. 安装 Python 依赖
pip3 install -r requirements.txt

# 3. 启动（项目根目录下执行）
PYTHONPATH=. python3 -m bridge.main --host 0.0.0.0 --port 8765
```

## 安装为 systemd 服务

```bash
# 需要 sudo，distro 默认为 humble
sudo bash install.sh humble

sudo systemctl start ros2-bridge
sudo systemctl status ros2-bridge
sudo journalctl -u ros2-bridge -f
```

## 实现新 ROS2 接口

每个 handler 文件中已标注 `TODO` 的位置需要填入实际 ROS2 消息类型和服务名。以 `voice.speak` 为例：

```python
# bridge/handlers/voice.py

@register("voice.speak")
async def speak(params: dict, adapter: Ros2Adapter) -> Any:
    text: str = params["text"]

    from walker_voice_msgs.srv import Speak          # 替换为实际消息包
    req = Speak.Request()
    req.text = text
    req.speed = params.get("speed", 50)
    req.volume = params.get("volume", 60)
    ros_result = await adapter.call_service(Speak, "/walker/voice/speak", req)
    return "accept" if ros_result.success else ros_result.message
```

## 新增 method

1. 在对应的 `handlers/*.py` 中添加函数并使用 `@register("module.method")` 装饰
2. 无需修改 `dispatcher.py` 或 `server.py`

```python
from bridge.dispatcher import register

@register("voice.greet")
async def greet(params: dict, adapter) -> Any:
    ...
```

## 协议格式

遵循 JSON-RPC 2.0 over WebSocket，详见 `docs/JSON-RPC协议设计.md`。

## 默认推送

- 桥启动后会默认订阅 `/emb/battery_state`
- 收到 `emb_task_msgs/msg/BatteryState` 后，会向所有在线 WebSocket 连接广播 `battery_state.data` 通知
- 桥启动后会默认订阅 `/sys/speech/mic_denoise`
- 收到 `std_msgs/msg/Int16MultiArray` 后，会向所有在线 WebSocket 连接广播 `mic.data` 通知
- 录音需要通过 `mic.record_start` / `mic.record_stop` 手动控制

**电池通知示例：**
```json
{
  "jsonrpc": "2.0",
  "method": "battery_state.data",
  "params": {
    "topic": "/emb/battery_state",
    "batteries_states": [
      {
        "charge_status": "charging",
        "voltage": 52.1,
        "current": 3.2,
        "temperature": 31.5,
        "maxdifvol": 0.04,
        "batsoc": 76.0,
        "remainchargetime": 18.0,
        "healthstatus": 0,
        "remainuselife": 420.0
      }
    ]
  }
}
```

**麦克风通知示例：**
```json
{
  "jsonrpc": "2.0",
  "method": "mic.data",
  "params": {
    "topic": "/sys/speech/mic_denoise",
    "layout": {
      "dim": [],
      "data_offset": 0
    },
    "data": [0, -2, 3, 1]
  }
}
```

## 动作播放协议

### 获取动作列表

请求：
```json
{"jsonrpc": "2.0", "id": 101, "method": "action.list", "params": {}}
```

成功响应：
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "result": {
    "list": [
      {"id": "wave_hand", "name": "挥手"}
    ]
  }
}
```

### 播放动作

请求：
```json
{
  "jsonrpc": "2.0",
  "id": 102,
  "method": "action.play",
  "params": {
    "action_id": "wave_hand",
    "params": {},
    "trace_id": "trace-001"
  }
}
```

成功响应：
```json
{
  "jsonrpc": "2.0",
  "id": 102,
  "result": {
    "trace_id": "trace-001",
    "type": "success",
    "start_utc_ms": 1710000000000,
    "end_utc_ms": 1710000003000,
    "succ_result": null,
    "fail_reason": null
  }
}
```

### 停止动作

请求：
```json
{"jsonrpc": "2.0", "id": 103, "method": "action.stop", "params": {"trace_id": "trace-001"}}
```

成功响应：
```json
{"jsonrpc": "2.0", "id": 103, "result": "accept"}
```

> `action.*` 当前 handler 中仍需填入实际 ROS2 service/action 类型后才能调用底层动作服务。

## 麦克风协议

### 默认监听

服务启动后会默认监听降噪麦克风话题：

```text
/sys/speech/mic_denoise
```

数据格式：

| 字段 | 值 |
|---|---|
| ROS2 message | `std_msgs/msg/Int16MultiArray` |
| JSON-RPC notification | `mic.data` |
| 采样率 | 16000 Hz |
| 通道数 | 1 |
| 采样格式 | int16 PCM |

### 手动订阅麦克风数据

请求：
```json
{
  "jsonrpc": "2.0",
  "id": 201,
  "method": "mic.subscribe",
  "params": {
    "topic": "/sys/speech/mic_denoise"
  }
}
```

成功响应：
```json
{
  "jsonrpc": "2.0",
  "id": 201,
  "result": {
    "status": "subscribed",
    "topic": "/sys/speech/mic_denoise"
  }
}
```

可订阅 topic：

| topic | 说明 |
|---|---|
| `/sys/speech/mic_source` | 原始 8 通道 16kHz 麦克风数据 |
| `/sys/speech/mic_denoise` | 降噪后 1 通道 16kHz 麦克风数据 |

### 取消麦克风订阅

请求：
```json
{
  "jsonrpc": "2.0",
  "id": 202,
  "method": "mic.unsubscribe",
  "params": {
    "topic": "/sys/speech/mic_denoise"
  }
}
```

成功响应：
```json
{
  "jsonrpc": "2.0",
  "id": 202,
  "result": {
    "status": "unsubscribed",
    "topic": "/sys/speech/mic_denoise"
  }
}
```

## 录音协议

录音功能保存默认降噪麦克风数据 `/sys/speech/mic_denoise`，需要通过 JSON-RPC 接口手动开始和停止。

### 手动开始录音

请求：
```json
{"jsonrpc": "2.0", "id": 301, "method": "mic.record_start", "params": {}}
```

成功响应：
```json
{
  "jsonrpc": "2.0",
  "id": 301,
  "result": {
    "active": true,
    "path": "recordings/20260513_193000_sys_speech_mic_denoise.wav",
    "topic": "/sys/speech/mic_denoise",
    "channels": 1,
    "sample_rate": 16000,
    "frames_written": 0,
    "duration_sec": 0.0,
    "started_at": "2026-05-13T19:30:00.000000"
  }
}
```

### 查看录音状态

请求：
```json
{"jsonrpc": "2.0", "id": 302, "method": "mic.record_status", "params": {}}
```

成功响应：
```json
{
  "jsonrpc": "2.0",
  "id": 302,
  "result": {
    "active": true,
    "path": "recordings/20260513_193000_sys_speech_mic_denoise.wav",
    "topic": "/sys/speech/mic_denoise",
    "channels": 1,
    "sample_rate": 16000,
    "frames_written": 16000,
    "duration_sec": 1.0,
    "started_at": "2026-05-13T19:30:00.000000"
  }
}
```

### 停止录音

请求：
```json
{"jsonrpc": "2.0", "id": 303, "method": "mic.record_stop", "params": {}}
```

成功响应：
```json
{
  "jsonrpc": "2.0",
  "id": 303,
  "result": {
    "active": true,
    "path": "recordings/20260513_193000_sys_speech_mic_denoise.wav",
    "topic": "/sys/speech/mic_denoise",
    "channels": 1,
    "sample_rate": 16000,
    "frames_written": 400000,
    "duration_sec": 25.0,
    "started_at": "2026-05-13T19:30:00.000000"
  }
}
```

录音文件说明：

| 字段 | 值 |
|---|---|
| 保存目录 | `recordings/` |
| 文件名 | `YYYYMMDD_HHMMSS_sys_speech_mic_denoise.wav` |
| 格式 | WAV |
| 编码 | PCM S16LE |
| 采样率 | 16000 Hz |
| 通道数 | 1 |

### 开始/结束录音 Demo

完整示例见 `examples/client_record_mic.py`。

启动桥服务后，在另一个终端运行：

```bash
python3 examples/client_record_mic.py --uri ws://localhost:8765 --duration 25
```

核心调用逻辑如下：

```python
import asyncio
import json

import websockets


async def call(ws, request):
    await ws.send(json.dumps(request, ensure_ascii=False))
    raw = await ws.recv()
    print(raw)
    return json.loads(raw)


async def main():
    async with websockets.connect("ws://127.0.0.1:8765") as ws:
        await call(ws, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "mic.record_start",
            "params": {}
        })

        await asyncio.sleep(25)

        await call(ws, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "mic.record_stop",
            "params": {}
        })


asyncio.run(main())
```

也可以在录音过程中查询状态：

```json
{"jsonrpc": "2.0", "id": 3, "method": "mic.record_status", "params": {}}
```


## 错误码

| code | 含义 |
|---|---|
| -32700 | Parse error |
| -32600 | Invalid Request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32000 | 业务错误 |



<!-- ubt@vision:~$ source /opt/ros/humble/setup.bash
ubt@vision:~$ PYTHONPATH=~:$PYTHONPATH python3 -m bridge.main -->
