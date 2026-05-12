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

**通知示例：**
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

**请求示例：**
```json
{"jsonrpc": "2.0", "id": 1, "method": "robotinfo.get_info", "params": {"client": "app"}}
```

**成功响应：**
```json
{"jsonrpc": "2.0", "id": 1, "result": {"model": "WalkerS2", "sn": "...", "version": "..."}}
```

**错误响应：**
```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "..."}}
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
