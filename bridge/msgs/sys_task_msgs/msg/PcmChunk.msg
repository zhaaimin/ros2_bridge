# 流式 PCM 音频数据块
# SDK → robot audio player node via /sys/pcm_stream

string   stream_id         # 流会话标识
uint64   seq               # 本流内自增序号（从 0 开始）
uint32   sample_rate       # 采样率，Hz（如 16000）
uint16   channels          # 声道数（如 1 = mono）
uint16   bits_per_sample   # 每采样位数（如 16）
uint8[]  data              # PCM 原始数据
bool     is_last           # true = 本流最后一个 chunk
