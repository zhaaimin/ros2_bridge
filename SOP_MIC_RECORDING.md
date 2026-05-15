# SOP: 客户端订阅麦克风数据与录音协议

本文档说明客户端如何通过 WebSocket JSON-RPC 调用桥服务，订阅麦克风数据并控制服务端录音。

## 1. 连接服务

服务端默认监听：

```text
ws://<server-ip>:8765
```

所有客户端请求使用 JSON-RPC 2.0 格式：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "method.name",
  "params": {}
}
```

服务端响应格式：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {}
}
```

服务端主动推送 notification 时没有 `id` 字段：

```json
{
  "jsonrpc": "2.0",
  "method": "mic.data",
  "params": {}
}
```

## 2. 麦克风 Topic

可订阅的麦克风 topic：

| topic | 说明 | ROS2 消息 | 采样率 | 通道数 |
|---|---|---|---|---|
| `/sys/speech/mic_source` | 原始麦克风数据 | `std_msgs/msg/Int16MultiArray` | 16000 Hz | 8 |
| `/sys/speech/mic_denoise` | 降噪后麦克风数据 | `std_msgs/msg/Int16MultiArray` | 16000 Hz | 1 |

服务启动后会默认监听 `/sys/speech/mic_denoise`。客户端只有发送 `mic.subscribe` 订阅后，才会收到该 topic 的 `mic.data` 推送。

## 3. 订阅麦克风数据

客户端发送：

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

服务端成功响应：

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

订阅成功后，服务端会向该客户端持续推送：

```json
{
  "jsonrpc": "2.0",
  "method": "mic.data",
  "params": {
    "topic": "/sys/speech/mic_denoise",
    "seq": 100,
    "dropped_count": 0,
    "queued_count": 0,
    "layout": {
      "dim": [],
      "data_offset": 0
    },
    "data": [0, -1, 2]
  }
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `topic` | 当前推送的麦克风 topic |
| `seq` | 服务端推送序号，主要用于排查是否连续 |
| `dropped_count` | 服务端麦克风推送队列满时丢弃的累计帧数 |
| `queued_count` | 当前待推送队列中的帧数 |
| `layout` | ROS2 `Int16MultiArray.layout` |
| `data` | int16 PCM 数据数组 |

客户端需要把 `data` 按 int16 PCM 处理。订阅 `/sys/speech/mic_denoise` 时是单通道 16kHz；订阅 `/sys/speech/mic_source` 时是 8 通道 16kHz。

## 4. 取消订阅麦克风数据

客户端发送：

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

服务端成功响应：

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

取消订阅后，该客户端不再收到该 topic 的 `mic.data` 推送。

## 5. 开始录音

录音功能保存服务端收到的降噪麦克风数据 `/sys/speech/mic_denoise`，文件格式为 WAV，编码为 PCM S16LE，采样率 16000 Hz，单通道。

客户端发送：

```json
{
  "jsonrpc": "2.0",
  "id": 301,
  "method": "mic.record_start",
  "params": {}
}
```

服务端成功响应：

```json
{
  "jsonrpc": "2.0",
  "id": 301,
  "result": {
    "active": true,
    "paused": false,
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

默认情况下，发起 `mic.record_start` 的客户端断开连接时，服务端会自动停止录音并关闭 WAV 文件。

如果希望客户端断开后继续录音，发送：

```json
{
  "jsonrpc": "2.0",
  "id": 301,
  "method": "mic.record_start",
  "params": {
    "auto_stop_on_disconnect": false
  }
}
```

## 6. 查询录音状态

客户端发送：

```json
{
  "jsonrpc": "2.0",
  "id": 302,
  "method": "mic.record_status",
  "params": {}
}
```

服务端成功响应：

```json
{
  "jsonrpc": "2.0",
  "id": 302,
  "result": {
    "active": true,
    "paused": false,
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

状态字段说明：

| 字段 | 说明 |
|---|---|
| `active` | 当前是否正在录音 |
| `paused` | 当前录音是否暂停 |
| `path` | 服务端本地 WAV 文件路径 |
| `topic` | 当前录音使用的 topic |
| `channels` | WAV 通道数 |
| `sample_rate` | WAV 采样率 |
| `frames_written` | 已写入 WAV 的采样帧数 |
| `duration_sec` | 根据 `frames_written / sample_rate` 计算的音频时长 |
| `started_at` | 服务端开始录音时间 |

## 7. 暂停录音

暂停后，服务端仍会继续接收麦克风数据，也会继续按客户端订阅推送 `mic.data`，但不会写入当前 WAV 文件。

客户端发送：

```json
{
  "jsonrpc": "2.0",
  "id": 303,
  "method": "mic.record_pause",
  "params": {}
}
```

服务端成功响应：

```json
{
  "jsonrpc": "2.0",
  "id": 303,
  "result": {
    "active": true,
    "paused": true,
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

## 8. 继续录音

客户端发送：

```json
{
  "jsonrpc": "2.0",
  "id": 304,
  "method": "mic.record_resume",
  "params": {}
}
```

服务端成功响应：

```json
{
  "jsonrpc": "2.0",
  "id": 304,
  "result": {
    "active": true,
    "paused": false,
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

## 9. 停止录音

客户端发送：

```json
{
  "jsonrpc": "2.0",
  "id": 305,
  "method": "mic.record_stop",
  "params": {}
}
```

服务端成功响应：

```json
{
  "jsonrpc": "2.0",
  "id": 305,
  "result": {
    "active": true,
    "paused": false,
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

`mic.record_stop` 返回的是停止前的最终录音状态。成功响应后 WAV 文件已经关闭，可在服务端 `path` 指向的位置读取。

## 10. 推荐客户端流程

只接收麦克风数据：

1. 建立 WebSocket 连接。
2. 发送 `mic.subscribe`，topic 使用 `/sys/speech/mic_denoise`。
3. 持续处理服务端推送的 `mic.data` notification。
4. 不再需要时发送 `mic.unsubscribe`。
5. 关闭 WebSocket。

录音并同时接收麦克风数据：

1. 建立 WebSocket 连接。
2. 发送 `mic.subscribe`，确保客户端能收到 `mic.data` 推送。
3. 发送 `mic.record_start`。
4. 按业务需要发送 `mic.record_pause` / `mic.record_resume`。
5. 发送 `mic.record_stop`，读取响应中的 `path` 和 `duration_sec`。
6. 发送 `mic.unsubscribe`。
7. 关闭 WebSocket。

只让服务端保存 WAV，不接收麦克风推送：

1. 建立 WebSocket 连接。
2. 发送 `mic.record_start`。
3. 发送 `mic.record_stop`。
4. 关闭 WebSocket。

## 11. 断连行为

默认行为：

| 场景 | 服务端行为 |
|---|---|
| 已订阅麦克风的客户端断开 | 服务端移除该客户端订阅，不再向该客户端推送 |
| 发起录音的客户端断开 | 服务端自动停止录音并关闭 WAV 文件 |
| 其他客户端断开 | 不影响当前录音 |
| `auto_stop_on_disconnect=false` 的录音客户端断开 | 录音继续，直到其他客户端或后续连接调用 `mic.record_stop` |

## 12. 错误响应

错误响应格式：

```json
{
  "jsonrpc": "2.0",
  "id": 301,
  "error": {
    "code": -32000,
    "message": "recording already active: recordings/20260513_193000_sys_speech_mic_denoise.wav"
  }
}
```

常见错误：

| 场景 | code | message 示例 |
|---|---|---|
| 方法不存在 | `-32601` | `Method not found: mic.xxx` |
| 参数错误 | `-32602` | `Invalid params: Invalid topic: ...` |
| 录音已经开始时再次开始 | `-32000` | `recording already active: ...` |
| 未开始录音时暂停、继续或停止 | `-32000` | `recording is not active` |
| JSON 格式错误 | `-32700` | `Parse error: ...` |

客户端处理建议：

1. 所有带 `id` 的请求都等待对应 `id` 的响应。
2. 收到没有 `id` 且 `method=mic.data` 的消息时，按麦克风帧处理。
3. 收到 `error` 时，不要继续假设命令已执行成功。
4. 录音相关命令建议串行发送，避免同时发送多个 `record_start` / `record_stop`。
