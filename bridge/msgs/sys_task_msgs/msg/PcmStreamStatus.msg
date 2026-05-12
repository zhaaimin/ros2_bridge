# 流式 PCM 播放状态反馈
# robot audio player node → SDK via /sys/pcm_stream_status

string   stream_id         # 流会话标识
uint8    state             # 状态码
uint8    PLAYING   = 0
uint8    FINISHED  = 1
uint8    ERROR     = 2
uint8    CANCELLED = 3
string   description       # 可选描述
uint64   played_samples    # 已播放采样数
uint64   buffered_samples  # 已缓冲采样数
