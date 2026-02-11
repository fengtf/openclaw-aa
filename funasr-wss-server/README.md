# FunASR WebSocket 服务器

基于阿里达摩院 FunASR 的实时语音识别 WebSocket 服务器。

## 功能特性

- 🎤 实时语音识别（流式处理）
- 📁 离线文件转写（接口预留）
- 🔌 WebSocket 协议支持
- ⚡ 低延迟识别
- 🚀 多客户端并发支持
- 🔧 可配置模型参数

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置服务器

编辑 `config.yaml` 文件，根据需要修改模型和服务器配置。

### 3. 启动服务器

```bash
python app.py
```

或使用 uvicorn:

```bash
uvicorn app:app --host 0.0.0.0 --port 10095 --reload
```

### 4. 使用客户端

#### 流式传输音频文件

```bash
python client.py
```

选择模式1，输入音频文件路径。

#### 实时麦克风输入

```bash
python client.py
```

选择模式2，开始说话（需安装 `pyaudio`）。

## API 接口

### WebSocket 端点
- `ws://localhost:10095/ws/asr` - 实时语音识别

### HTTP 接口
- `GET /` - 服务器状态
- `GET /health` - 健康检查
- `POST /api/asr` - 离线文件转写（待实现）

## 配置说明

### 服务器配置 (`config.yaml`)

```yaml
server:
  host: "0.0.0.0"       # 监听地址
  port: 10095           # 监听端口
  chunk_duration_ms: 600 # 每个chunk的时长（毫秒）
  sample_rate: 16000    # 音频采样率

models:
  asr_model: "paraformer-zh-streaming"  # ASR模型
  vad_model: "fsmn-vad"                 # VAD模型（可选）
  punc_model: "ct-punc"                 # 标点模型（可选）
  device: "cpu"                         # 运行设备
```

### 支持的模型

1. **实时识别模型**: `paraformer-zh-streaming` - 中文流式识别
2. **离线识别模型**: `paraformer-zh`、`SenseVoiceSmall`、`Fun-ASR-Nano`
3. **辅助模型**: `fsmn-vad`（VAD）、`ct-punc`（标点）

## 客户端开发

### WebSocket 通信协议

1. 连接: `ws://server:port/ws/asr`
2. 发送二进制音频（16bit PCM，16kHz），每 chunk 建议 600ms（9600 采样点）
3. 结束时可发送 JSON 文本: `{"action": "end"}`
4. 服务端返回 JSON 识别结果

#### 响应格式
```json
{
  "text": "识别出的文字",
  "is_final": false,
  "timestamp": "2023-12-01T10:30:00",
  "chunk_id": 1
}
```

## 性能优化建议

1. **GPU 加速**: 在 `config.yaml` 中设置 `device: "cuda:0"`
2. **模型量化**: `funasr-export ++model=paraformer ++quantize=true`

## 故障排除

1. **模型下载失败**: 检查网络，必要时配置代理或从 ModelScope 手动下载
2. **内存不足**: 使用量化模型或减小 chunk 相关参数
3. **音频质量差**: 保证 16kHz、单声道

## 参考

- [FunASR GitHub](https://github.com/alibaba-damo-academy/FunASR)
- [ModelScope](https://modelscope.cn)
