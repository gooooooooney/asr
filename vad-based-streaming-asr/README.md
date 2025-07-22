# VAD-Based Streaming ASR

基于语音活动检测（VAD）的流式语音识别系统，使用WebSocket实现实时音频传输和处理。

## 功能特性

- ✅ 实时音频流传输（WebSocket）
- ✅ 智能VAD语音切分
- ✅ Whisper V3语音识别（通过Fireworks API）
- ✅ 上下文prompt优化
- ✅ 可选的LLM文本修正
- ✅ 超时切分和中断重识别
- ✅ 实时延迟监控

## 快速开始

### 1. 安装依赖

```bash
pip install websockets numpy requests
```

### 2. 获取API密钥

需要从 [Fireworks AI](https://app.fireworks.ai/) 获取API密钥。

### 3. 启动服务器

```bash
python server_main.py
```

服务器将同时启动：
- HTTP服务器：http://localhost:8080
- WebSocket服务器：ws://localhost:8765

### 4. 打开网页

在浏览器中访问：http://localhost:8080/index.html

### 5. 使用步骤

1. 输入Fireworks API密钥
2. 点击"连接"按钮连接到服务器
3. （可选）勾选"启用LLM文本修正"
4. 点击"开始录音"开始语音识别
5. 说话时会实时显示识别结果

## 系统架构

```
浏览器客户端                    服务器端
    │                           │
    ├─ 音频采集 (16kHz)         ├─ WebSocket服务器
    ├─ WebSocket客户端          ├─ VAD处理器
    └─ UI显示                   ├─ Whisper客户端
                                └─ LLM处理器
```

## 核心算法

### VAD切分逻辑

1. **基础切分**：检测到从"有语音"到"无语音"的状态转换时切分
2. **超时切分**：连续3秒未检测到静音时强制切分
3. **中断重识别**：遇到VAD中断时，重新识别最近的音频片段并覆盖之前的结果

### Prompt优化

使用前两句已识别的内容作为Whisper的prompt，提高识别准确率。

## 配置参数

```python
# server.py 中的默认配置
MAX_SEGMENT_DURATION = 3.0  # 最大片段时长（秒）
LOOKBACK_DURATION = 9.0     # 重识别回看时长（秒）
VAD_THRESHOLD = 0.5         # VAD阈值
SILENCE_DURATION = 0.8      # 静音判定时长（秒）
```

## 注意事项

1. 需要HTTPS环境才能使用麦克风权限（本地开发除外）
2. 建议使用Chrome或Edge浏览器
3. 确保麦克风权限已授予
4. API调用会产生费用，请注意使用量

## 故障排除

### 无法连接WebSocket
- 检查服务器是否正常启动
- 确认端口8765和8080未被占用
- 检查防火墙设置

### 无法访问麦克风
- 检查浏览器麦克风权限
- 确保没有其他应用占用麦克风
- 尝试使用HTTPS（生产环境）

### 识别效果不佳
- 检查环境噪音
- 调整VAD阈值
- 确保说话音量适中

## 开发说明

### 文件结构
```
vad-based-streaming-asr/
├── server.py          # WebSocket服务器实现
├── server_main.py     # 主服务器入口
├── index.html         # 网页客户端
├── README.md          # 本文档
└── 技术报告.md        # 详细技术文档
```

### 扩展开发

1. **集成真实的TEN-VAD**：当前使用简化的音量检测，可替换为真实的TEN-VAD
2. **LLM集成**：当前LLM修正为模拟实现，可接入真实的LLM服务
3. **多语言支持**：可扩展支持其他语言的识别和修正
4. **性能优化**：添加音频压缩、批量处理等优化

## 许可证

MIT License