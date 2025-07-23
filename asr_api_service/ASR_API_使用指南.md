# ASR API 服务使用指南

## 概述

ASR API 服务提供了两种主要的接口：
1. **REST API** - 用于批量音频文件转写
2. **WebSocket API** - 用于实时流式语音识别

## 1. REST API 接口

### 1.1 健康检查

```bash
# 检查服务状态
curl http://localhost:8000/health
```

### 1.2 音频文件转写

```python
import requests

# 上传音频文件进行转写
def transcribe_audio_file(file_path):
    """
    转写音频文件
    
    参数:
        file_path: 音频文件路径（支持WAV格式）
    """
    url = "http://localhost:8000/api/v1/transcribe"
    
    with open(file_path, "rb") as f:
        files = {"audio": f}
        data = {
            "prompt": "",  # 可选：提供上下文提示
            "language": "zh",  # 可选：指定语言（zh=中文，en=英文）
            "enable_llm": False  # 可选：是否启用LLM纠错
        }
        
        response = requests.post(url, files=files, data=data)
        
    if response.status_code == 200:
        result = response.json()
        print(f"转写结果: {result['text']}")
        print(f"处理时间: {result['processing_time_ms']}ms")
    else:
        print(f"错误: {response.json()}")
```

### 1.3 原始音频数据转写

```python
import numpy as np
import requests

def transcribe_raw_audio(audio_data, sample_rate=16000):
    """
    转写原始音频数据
    
    参数:
        audio_data: 音频数据数组（浮点数列表）
        sample_rate: 采样率（默认16000）
    """
    url = "http://localhost:8000/api/v1/transcribe-raw"
    
    # 准备请求数据
    request_data = {
        "request": {
            "prompt": "",
            "language": "zh",
            "enable_llm": False
        },
        "audio_data": audio_data.tolist() if isinstance(audio_data, np.ndarray) else audio_data,
        "sample_rate": sample_rate
    }
    
    response = requests.post(url, json=request_data)
    
    if response.status_code == 200:
        result = response.json()
        return result
    else:
        raise Exception(f"转写失败: {response.json()}")
```

### 1.4 查询可用模型

```python
# 获取支持的ASR模型列表
response = requests.get("http://localhost:8000/api/v1/models")
models = response.json()
print(f"默认模型: {models['default_model']}")
print(f"支持的语言: {models['models'][0]['languages']}")
```

## 2. VAD（语音活动检测）API

### 2.1 单次VAD检测

```python
import requests

# 检测音频中是否包含语音
def detect_voice_activity(audio_data, sample_rate=16000):
    """
    检测音频中的语音活动
    
    参数:
        audio_data: 音频数据（-1.0到1.0的浮点数列表）
        sample_rate: 采样率
    """
    url = "http://localhost:8000/api/v1/vad/detect"
    
    response = requests.post(url, json={
        "audio_data": audio_data,
        "sample_rate": sample_rate
    })
    
    if response.status_code == 200:
        result = response.json()
        print(f"是否在说话: {result['is_speaking']}")
        print(f"状态: {result['state']}")  # 'speech' 或 'silence'
        print(f"概率: {result['probability']}")
        print(f"RMS能量: {result['rms']}")
        print(f"状态是否改变: {result['state_changed']}")
        return result
    else:
        print(f"错误: {response.json()}")
```

### 2.2 批量处理音频片段

```python
# 批量处理多个音频片段
def process_audio_segments(segments, sample_rate=16000):
    """
    批量处理多个音频片段的VAD检测
    
    参数:
        segments: 音频片段列表
        sample_rate: 采样率
    """
    url = "http://localhost:8000/api/v1/vad/process-segments"
    
    response = requests.post(url, json={
        "segments": segments,
        "sample_rate": sample_rate,
        "reset_between_segments": False  # 是否在片段间重置VAD状态
    })
    
    if response.status_code == 200:
        result = response.json()
        print(f"处理了 {result['summary']['total_segments']} 个片段")
        print(f"语音片段: {result['summary']['speech_segments']}")
        print(f"静音片段: {result['summary']['silence_segments']}")
        print(f"语音比例: {result['summary']['speech_ratio']}")
        
        # 查看每个片段的结果
        for seg in result['segments']:
            print(f"片段 {seg['segment_index']}: {seg['state']}")
```

### 2.3 分析完整音频文件

```python
# 分析音频文件中的语音活动分布
def analyze_audio_file(audio_data, sample_rate=16000):
    """
    分析整个音频文件，提取语音段时间戳
    
    参数:
        audio_data: 完整音频文件数据
        sample_rate: 采样率
    """
    url = "http://localhost:8000/api/v1/vad/analyze-file"
    
    response = requests.post(url, json={
        "audio_data": audio_data,
        "sample_rate": sample_rate,
        "window_duration": 0.5,  # 分析窗口时长（秒）
        "overlap": 0.1          # 窗口重叠（秒）
    })
    
    if response.status_code == 200:
        result = response.json()
        
        # 统计信息
        stats = result['statistics']
        print(f"总时长: {stats['total_duration']}秒")
        print(f"语音时长: {stats['total_speech_duration']}秒")
        print(f"语音比例: {stats['speech_ratio']}")
        
        # 语音段列表
        print(f"\n检测到 {len(result['speech_segments'])} 个语音段:")
        for seg in result['speech_segments']:
            print(f"  {seg['start']}s - {seg['end']}s (时长: {seg['duration']}s)")
```

### 2.4 实时VAD处理示例

```python
import numpy as np
import pyaudio
import requests
import threading
import queue

class RealtimeVAD:
    def __init__(self):
        self.sample_rate = 16000
        self.chunk_size = 1600  # 100ms @ 16kHz
        self.audio = pyaudio.PyAudio()
        self.vad_queue = queue.Queue()
        
    def process_vad(self):
        """VAD处理线程"""
        url = "http://localhost:8000/api/v1/vad/detect"
        
        while self.running:
            try:
                audio_chunk = self.vad_queue.get(timeout=1)
                
                response = requests.post(url, json={
                    "audio_data": audio_chunk,
                    "sample_rate": self.sample_rate
                })
                
                if response.status_code == 200:
                    result = response.json()
                    if result['state_changed']:
                        state = "开始说话" if result['is_speaking'] else "停止说话"
                        print(f"[VAD] {state}")
                        
            except queue.Empty:
                continue
    
    def record_with_vad(self, duration=10):
        """录音并进行实时VAD检测"""
        self.running = True
        
        # 启动VAD处理线程
        vad_thread = threading.Thread(target=self.process_vad)
        vad_thread.start()
        
        # 开始录音
        stream = self.audio.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        print("开始录音和VAD检测...")
        
        try:
            start_time = time.time()
            while time.time() - start_time < duration:
                # 读取音频
                audio_data = stream.read(self.chunk_size)
                audio_array = np.frombuffer(audio_data, dtype=np.float32)
                
                # 发送到VAD队列
                self.vad_queue.put(audio_array.tolist())
                
        finally:
            self.running = False
            stream.stop_stream()
            stream.close()
            vad_thread.join()
            
        print("录音结束")
```

### 2.5 VAD状态管理

```python
# 获取VAD状态
response = requests.get("http://localhost:8000/api/v1/vad/status")
status = response.json()
print(f"VAD类型: {status['current_state']['vad_type']}")
print(f"配置: {status['configuration']}")

# 重置VAD状态
response = requests.post("http://localhost:8000/api/v1/vad/reset")
print("VAD状态已重置")
```

## 3. WebSocket 流式API

### 3.1 基本使用流程

```python
import asyncio
import json
import websockets

class ASRStreamingClient:
    def __init__(self, server_url="ws://localhost:8000/api/v1/stream"):
        self.server_url = server_url
        self.websocket = None
        
    async def connect(self, api_key):
        """连接到流式ASR服务"""
        # 1. 建立WebSocket连接
        self.websocket = await websockets.connect(self.server_url)
        
        # 2. 发送配置信息
        config = {
            "type": "config",
            "data": {
                "api_key": api_key,  # API密钥
                "enable_llm": True,  # 启用LLM纠错
                "language": "zh"     # 设置语言为中文
            },
            "timestamp": int(time.time() * 1000)
        }
        await self.websocket.send(json.dumps(config))
        
        # 3. 等待服务器就绪
        response = await self.websocket.recv()
        message = json.loads(response)
        if message["type"] == "status" and message["data"]["status"] == "ready":
            print("服务器已就绪")
            return True
        return False
    
    async def send_audio_stream(self, audio_chunks):
        """发送音频流"""
        # 发送开始录音命令
        await self.websocket.send(json.dumps({
            "type": "control",
            "data": {"command": "start"},
            "timestamp": int(time.time() * 1000)
        }))
        
        # 流式发送音频数据
        for chunk in audio_chunks:
            audio_message = {
                "type": "audio",
                "data": {
                    "audio_data": chunk.tolist(),  # 音频数据（浮点数数组）
                    "sample_rate": 16000           # 采样率
                },
                "timestamp": int(time.time() * 1000)
            }
            await self.websocket.send(json.dumps(audio_message))
            
            # 模拟实时流，稍作延迟
            await asyncio.sleep(0.1)
        
        # 发送停止录音命令
        await self.websocket.send(json.dumps({
            "type": "control",
            "data": {"command": "stop"},
            "timestamp": int(time.time() * 1000)
        }))
    
    async def receive_results(self):
        """接收转写结果"""
        while True:
            try:
                response = await self.websocket.recv()
                message = json.loads(response)
                
                if message["type"] == "result":
                    # 转写结果
                    data = message["data"]
                    text = data.get("text", "")
                    corrected_text = data.get("corrected_text")  # LLM纠错后的文本
                    is_final = data.get("is_final", False)       # 是否为最终结果
                    
                    if corrected_text:
                        print(f"纠错结果: {corrected_text}")
                    else:
                        print(f"识别结果: {text}")
                    
                    if is_final:
                        print("--- 段落结束 ---")
                        
                elif message["type"] == "status":
                    # 状态更新
                    data = message["data"]
                    if "vad_state" in data:
                        # VAD状态变化
                        vad = data["vad_state"]
                        if vad.get("state_changed"):
                            state = vad.get("current_state")
                            print(f"VAD状态: {'说话中' if state == 'speech' else '静音'}")
                            
                elif message["type"] == "error":
                    # 错误信息
                    print(f"错误: {message['data']['error']}")
                    
            except websockets.exceptions.ConnectionClosed:
                print("连接已关闭")
                break
```

### 3.2 完整示例：实时语音识别

```python
import asyncio
import numpy as np
import pyaudio
import websockets
import json
import time

class RealtimeASR:
    def __init__(self):
        self.sample_rate = 16000
        self.chunk_size = 512  # 32ms @ 16kHz
        self.audio = pyaudio.PyAudio()
        
    async def record_and_transcribe(self, api_key):
        """录音并实时转写"""
        # 创建WebSocket连接
        async with websockets.connect("ws://localhost:8000/api/v1/stream") as ws:
            # 发送配置
            await ws.send(json.dumps({
                "type": "config",
                "data": {
                    "api_key": api_key,
                    "enable_llm": True,
                    "language": "zh"
                },
                "timestamp": int(time.time() * 1000)
            }))
            
            # 等待就绪
            ready_msg = await ws.recv()
            print("服务器状态:", json.loads(ready_msg))
            
            # 开始录音
            stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            print("开始录音...（按Ctrl+C停止）")
            
            # 启动结果接收任务
            async def receive_results():
                while True:
                    try:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if data["type"] == "result":
                            result = data["data"]
                            text = result.get("corrected_text") or result.get("text")
                            if text:
                                print(f"\r{'[最终]' if result.get('is_final') else '[临时]'} {text}", end='')
                                if result.get('is_final'):
                                    print()  # 换行
                                    
                    except Exception as e:
                        print(f"\n接收错误: {e}")
                        break
            
            # 创建接收任务
            receive_task = asyncio.create_task(receive_results())
            
            # 发送开始命令
            await ws.send(json.dumps({
                "type": "control",
                "data": {"command": "start"},
                "timestamp": int(time.time() * 1000)
            }))
            
            try:
                # 持续发送音频数据
                while True:
                    # 读取音频数据
                    audio_data = stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_array = np.frombuffer(audio_data, dtype=np.float32)
                    
                    # 发送音频
                    await ws.send(json.dumps({
                        "type": "audio",
                        "data": {
                            "audio_data": audio_array.tolist(),
                            "sample_rate": self.sample_rate
                        },
                        "timestamp": int(time.time() * 1000)
                    }))
                    
                    # 小延迟避免过快发送
                    await asyncio.sleep(0.01)
                    
            except KeyboardInterrupt:
                print("\n停止录音...")
                
            finally:
                # 发送停止命令
                await ws.send(json.dumps({
                    "type": "control",
                    "data": {"command": "stop"},
                    "timestamp": int(time.time() * 1000)
                }))
                
                # 清理
                stream.stop_stream()
                stream.close()
                receive_task.cancel()
    
    def __del__(self):
        self.audio.terminate()

# 使用示例
async def main():
    api_key = "your_api_key_here"  # 替换为实际的API密钥
    asr = RealtimeASR()
    await asr.record_and_transcribe(api_key)

if __name__ == "__main__":
    # 需要安装：pip install pyaudio numpy websockets
    asyncio.run(main())
```

## 3. 消息格式说明

### 3.1 客户端消息类型

#### 配置消息
```json
{
    "type": "config",
    "data": {
        "api_key": "your_api_key",     // 必需：API密钥
        "enable_llm": true,            // 可选：启用LLM纠错
        "language": "zh",              // 可选：语言代码
        "vad_threshold": 0.5,          // 可选：VAD阈值
        "silence_duration": 0.8        // 可选：静音时长（秒）
    },
    "timestamp": 1234567890
}
```

#### 音频数据消息
```json
{
    "type": "audio",
    "data": {
        "audio_data": [0.1, -0.2, ...],  // 音频样本（-1.0到1.0的浮点数）
        "sample_rate": 16000             // 采样率
    },
    "timestamp": 1234567890
}
```

#### 控制命令消息
```json
{
    "type": "control",
    "data": {
        "command": "start"  // 可选值：start, stop, reset
    },
    "timestamp": 1234567890
}
```

### 3.2 服务器响应类型

#### 转写结果
```json
{
    "type": "result",
    "data": {
        "text": "识别的文本",              // 原始识别结果
        "corrected_text": "纠错后的文本",  // LLM纠错结果（如果启用）
        "is_final": true,                  // 是否为最终结果
        "is_reprocessed": false,           // 是否为重新处理的结果
        "confidence": 0.95,                // 置信度
        "chunk_id": "chunk_123",           // 音频块ID
        "processing_time_ms": 150          // 处理时间
    },
    "timestamp": 1234567890
}
```

#### 状态消息
```json
{
    "type": "status",
    "data": {
        "status": "ready",  // 系统状态
        "vad_state": {      // VAD状态信息
            "current_state": "speech",  // speech 或 silence
            "state_changed": true,      // 状态是否改变
            "duration_ms": 1500         // 当前状态持续时间
        }
    },
    "timestamp": 1234567890
}
```

#### 错误消息
```json
{
    "type": "error",
    "data": {
        "error": "错误描述",
        "error_code": "ERROR_CODE",
        "details": { ... }
    },
    "timestamp": 1234567890
}
```

## 4. 最佳实践

### 4.1 音频格式建议
- **采样率**: 16000 Hz（推荐）
- **通道数**: 单声道（1通道）
- **位深度**: 16位或32位浮点
- **格式**: PCM原始数据或WAV

### 4.2 性能优化
1. **批量发送**: 将音频数据分块发送，每块0.5-1秒
2. **缓冲管理**: 保持适当的音频缓冲，避免丢失
3. **网络优化**: 使用稳定的网络连接，考虑使用压缩

### 4.3 错误处理
```python
try:
    # API调用
    response = await client.send_audio(audio_data)
except websockets.exceptions.ConnectionClosed:
    print("连接断开，尝试重连...")
    await client.reconnect()
except Exception as e:
    print(f"发生错误: {e}")
    # 记录错误日志
    # 实施重试策略
```

## 5. 常见问题

### Q1: 支持哪些音频格式？
A: 目前REST API仅支持WAV格式，WebSocket API支持原始PCM数据。

### Q2: 如何提高识别准确率？
A: 
- 使用高质量的音频输入（16kHz以上）
- 启用VAD避免静音段干扰
- 提供相关的prompt上下文
- 启用LLM纠错功能

### Q3: WebSocket连接断开怎么办？
A: 实现自动重连机制，保存会话状态，断线后恢复。

### Q4: 如何处理长音频？
A: 使用流式API分块发送，避免一次性加载大文件。

## 6. 部署配置

### 环境变量设置
```bash
# API配置
export API_HOST=0.0.0.0
export API_PORT=8000

# ASR服务配置
export WHISPER_API_KEY=your_key
export WHISPER_API_URL=https://api.openai.com/v1/audio/transcriptions

# VAD配置
export VAD_THRESHOLD=0.5
export VAD_SILENCE_DURATION=0.8

# 音频配置
export AUDIO_SAMPLE_RATE=16000
export AUDIO_CHUNK_DURATION=3.0
```

### Docker部署
```bash
# 构建镜像
docker build -t asr-api-service .

# 运行容器
docker run -p 8000:8000 \
  -e WHISPER_API_KEY=$WHISPER_API_KEY \
  -v ./data:/app/data \
  asr-api-service
```

## 7. 监控和日志

### 查看服务状态
```python
# 获取流式服务统计
response = requests.get("http://localhost:8000/api/v1/streaming-stats")
stats = response.json()
print(f"活跃客户端: {stats['active_clients']}")
print(f"总连接数: {stats['total_connections']}")
print(f"平均处理时间: {stats['average_processing_time_ms']}ms")
```

### 查看活跃客户端
```python
response = requests.get("http://localhost:8000/api/v1/active-clients")
clients = response.json()
for client in clients['clients']:
    print(f"客户端ID: {client['client_id']}")
    print(f"连接时间: {client['connected_at']}")
    print(f"消息数: {client['total_messages']}")
```