# 移动端专用 API 使用指南 (Expo React Native)

## API 概述

本指南专门针对 **Expo React Native** 应用开发，使用 **@siteed/expo-audio-studio** 进行音频录制，并与 ASR API 服务集成进行语音活动检测(VAD)和音频处理。

### 核心特性

1. **高质量音频录制** - 使用 expo-audio-stream 进行专业级录音
2. **实时 VAD 检测** - 集成 TEN-VAD 进行精确语音检测  
3. **多种传输方式** - REST API、WebSocket流式处理
4. **格式自动转换** - 支持多种音频格式转换
5. **性能优化** - 避免Base64膨胀，提升传输效率

## 依赖安装

```bash
# 安装必需的包
npm install @siteed/expo-audio-studio expo-audio expo-file-system

# 如果使用WebSocket
npm install ws
```

## API 端点概览

本文档涵盖三种主要的音频处理方式：
1. **HTTP REST API** - 适合录音完成后的批量处理
2. **WebSocket流式API** - 适合实时音频流处理
3. **优化文件上传API** - 避免Base64编码，性能最佳

### 1. 主要处理端点：`/api/v1/mobile/process-audio`

这是最主要的端点，提供完整的音频处理功能。

#### 请求格式

```typescript
interface MobileAudioRequest {
  // 必需字段
  audio_base64: string;    // Base64 编码的音频数据
  format: string;          // 音频格式: "wav", "m4a", "mp3", "webm" 等
  sample_rate: number;     // 采样率，默认 16000
  
  // VAD 参数
  enable_vad: boolean;           // 是否启用 VAD，默认 true
  vad_window_duration: number;   // VAD 窗口时长（秒），默认 0.5
  vad_overlap: number;           // VAD 窗口重叠（秒），默认 0.1
  
  // 返回选项
  return_format: string;    // "segments" | "base64" | "merged"
  compress_output: boolean; // 是否压缩输出，默认 false
}
```

#### 响应格式

```typescript
interface MobileAudioResponse {
  success: boolean;
  message: string;
  
  // VAD 结果
  has_speech: boolean;              // 是否检测到语音
  speech_segments: Array<{          // 语音段列表
    start: number;
    end: number;
    duration: number;
  }>;
  speech_ratio: number;             // 语音占比 (0-1)
  total_duration: number;           // 总时长（秒）
  
  // 音频数据（根据 return_format）
  audio_data?: number[];            // PCM 浮点数组
  audio_base64?: string;            // Base64 编码的音频
  audio_format?: string;            // 音频格式
  
  // 性能指标
  processing_time_ms: number;       // 处理时间
  audio_size_bytes?: number;        // 音频大小
}
```

#### 使用示例

```javascript
// Expo React Native 中的使用
import * as FileSystem from 'expo-file-system';
import axios from 'axios';

async function processRecording(audioUri) {
  // 读取录音文件
  const audioBase64 = await FileSystem.readAsStringAsync(audioUri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  
  // 发送到 API
  const response = await axios.post('http://your-api.com/api/v1/mobile/process-audio', {
    audio_base64: audioBase64,
    format: 'm4a',  // Expo 默认录制格式
    sample_rate: 16000,
    enable_vad: true,
    return_format: 'base64',  // 返回处理后的音频
  });
  
  if (response.data.success && response.data.has_speech) {
    console.log('检测到语音，时长:', response.data.total_duration);
    console.log('语音段:', response.data.speech_segments);
    
    // 使用处理后的音频
    const processedAudio = response.data.audio_base64;
    // 发送到后端或播放
  }
}
```

### 2. 快速检测端点：`/api/v1/mobile/quick-vad`

用于快速检测音频是否包含语音，响应极快。

#### 请求（Form Data）

```javascript
const formData = new FormData();
formData.append('audio_base64', audioBase64String);
formData.append('format', 'wav');
formData.append('sample_rate', '16000');

const response = await fetch('/api/v1/mobile/quick-vad', {
  method: 'POST',
  body: formData,
});
```

#### 响应

```json
{
  "has_speech": true,
  "rms": 0.125,
  "duration": 3.5,
  "processing_time_ms": 45
}
```

### 3. 批量处理端点：`/api/v1/mobile/batch-process`

处理多个音频文件，可选择合并结果。

#### 使用示例

```javascript
const formData = new FormData();

// 添加多个音频文件
audioFiles.forEach((file, index) => {
  formData.append('audio_files', file);
});

formData.append('enable_vad', 'true');
formData.append('merge_results', 'true');  // 合并所有有效音频

const response = await fetch('/api/v1/mobile/batch-process', {
  method: 'POST',
  body: formData,
});

const result = await response.json();
// result.merged_audio 包含合并后的音频
```

### 4. 高效处理端点：`/api/v1/mobile/process-audio-efficient` ⚡

**推荐使用**：避免Base64编码，直接文件上传，性能提升33%。

#### 请求格式

```javascript
// 使用 FormData 直接上传文件
const formData = new FormData();
formData.append('audio', {
  uri: audioUri,        // 音频文件路径
  type: 'audio/wav',    // MIME类型
  name: 'recording.wav', // 文件名
});
formData.append('sample_rate', '16000');
formData.append('enable_vad', 'true');
formData.append('return_audio', 'false');  // 是否返回处理后的音频
formData.append('output_format', 'json');  // 'json' 或 'binary'

const response = await fetch('/api/v1/mobile/process-audio-efficient', {
  method: 'POST',
  body: formData,
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});
```

#### 优势

- ✅ **性能提升33%** - 无Base64编码开销
- ✅ **内存使用减半** - 避免数据重复存储
- ✅ **支持所有格式** - WAV, M4A, MP3, OGG等
- ✅ **移动端友好** - 直接使用录音文件

### 5. WebSocket流式VAD处理 🚀

适用于**实时音频处理**，性能提升228%。

#### 连接地址

```javascript
// JSON格式流（调试友好）
const wsUrl = 'ws://your-api.com/api/v1/stream/vad';

// 二进制格式流（最高性能）
const wsUrl = 'ws://your-api.com/api/v1/stream/vad-binary';
```

#### WebSocket JSON流使用示例

```javascript
import WebSocket from 'ws';

class StreamVADProcessor {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.setupEventHandlers();
  }

  setupEventHandlers() {
    this.ws.onopen = () => {
      console.log('WebSocket连接建立');
      
      // 发送配置
      this.ws.send(JSON.stringify({
        type: 'config',
        sample_rate: 16000,
        channels: 1
      }));
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      switch (message.type) {
        case 'status':
          console.log('状态:', message.message);
          console.log('使用TEN-VAD:', message.use_real_vad);
          break;
          
        case 'vad':
          console.log('VAD结果:', {
            is_speaking: message.is_speaking,
            probability: message.probability,
            current_state: message.current_state,
            processing_time: message.processing_time_ms
          });
          
          // 根据VAD结果进行处理
          if (message.is_speaking) {
            this.onSpeechDetected(message);
          } else {
            this.onSilenceDetected(message);
          }
          break;
          
        case 'error':
          console.error('处理错误:', message.message);
          break;
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket连接关闭');
    };
  }

  // 发送音频数据
  sendAudioChunk(audioFloatArray) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'audio',
        data: Array.from(audioFloatArray)
      }));
    }
  }

  // 结束处理
  endProcessing() {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'end'
      }));
    }
  }

  onSpeechDetected(vadResult) {
    // 检测到语音时的处理逻辑
    console.log(`检测到语音 (置信度: ${vadResult.probability})`);
  }

  onSilenceDetected(vadResult) {
    // 检测到静音时的处理逻辑
    if (vadResult.silence_timeout) {
      console.log('静音超时，可能语音结束');
    }
  }

  close() {
    this.ws.close();
  }
}

// 使用示例
const vadProcessor = new StreamVADProcessor('ws://localhost:8000/api/v1/stream/vad');

// 模拟实时音频流
const simulateAudioStream = () => {
  const sampleRate = 16000;
  const chunkSize = 1024;
  
  setInterval(() => {
    // 生成模拟音频数据（实际应用中从麦克风获取）
    const audioChunk = new Float32Array(chunkSize);
    for (let i = 0; i < chunkSize; i++) {
      audioChunk[i] = (Math.random() - 0.5) * 0.1; // 随机噪音
    }
    
    vadProcessor.sendAudioChunk(audioChunk);
  }, (chunkSize / sampleRate) * 1000); // 实时速度
};

// 开始模拟
simulateAudioStream();
```

#### WebSocket二进制流使用示例（最高性能）

```javascript
class BinaryStreamVADProcessor {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.configured = false;
    this.setupEventHandlers();
  }

  setupEventHandlers() {
    this.ws.onopen = () => {
      // 发送配置（文本格式）
      this.ws.send(JSON.stringify({
        sample_rate: 16000,
        window_size: 1024
      }));
    };

    this.ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        // 配置响应或VAD结果
        const message = JSON.parse(event.data);
        
        if (message.type === 'ready') {
          console.log('WebSocket配置完成:', message);
          this.configured = true;
        } else {
          // VAD处理结果
          console.log('VAD结果:', {
            is_speaking: message.is_speaking,
            probability: message.probability,
            processing_time: message.processing_time_ms,
            samples: message.samples
          });
        }
      }
    };
  }

  // 发送二进制音频数据
  sendAudioBinary(audioFloatArray) {
    if (this.configured && this.ws.readyState === WebSocket.OPEN) {
      // 直接发送Float32数组的二进制数据
      const buffer = audioFloatArray.buffer;
      this.ws.send(buffer);
    }
  }

  // 结束处理
  endProcessing() {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(new ArrayBuffer(0)); // 空buffer表示结束
    }
  }
}

// 使用示例
const binaryProcessor = new BinaryStreamVADProcessor('ws://localhost:8000/api/v1/stream/vad-binary');

// 实时音频处理
const processRealTimeAudio = (audioBuffer) => {
  const float32Array = new Float32Array(audioBuffer);
  binaryProcessor.sendAudioBinary(float32Array);
};
```

### 实时WebSocket流式VAD组件

```typescript
// StreamingVADComponent.tsx
import React, { useEffect, useState, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { 
  useAudioRecorder, 
  RecordingConfig,
  ExpoAudioStreamModule 
} from '@siteed/expo-audio-studio';

interface VADResult {
  is_speaking: boolean;
  probability: number;
  current_state: string;
  processing_time_ms: number;
}

const API_WS_URL = 'ws://your-api.com';

export function StreamingVADComponent() {
  const [isConnected, setIsConnected] = useState(false);
  const [vadResult, setVadResult] = useState<VADResult | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioBufferRef = useRef<Float32Array[]>([]);
  
  // 使用 expo-audio-studio 进行实时录音
  const {
    startRecording,
    stopRecording,
    isRecording,
    durationMs,
  } = useAudioRecorder();

  const connectWebSocket = () => {
    try {
      const ws = new WebSocket(`${API_WS_URL}/api/v1/stream/vad`);
      
      ws.onopen = () => {
        console.log('WebSocket连接成功');
        setIsConnected(true);
        setConnectionError(null);
        
        // 发送配置
        ws.send(JSON.stringify({
          type: 'config',
          sample_rate: 16000,
          channels: 1
        }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          switch (message.type) {
            case 'status':
              console.log('WebSocket状态:', message.message);
              console.log('使用TEN-VAD:', message.use_real_vad);
              break;
              
            case 'vad':
              setVadResult({
                is_speaking: message.is_speaking,
                probability: message.probability,
                current_state: message.current_state,
                processing_time_ms: message.processing_time_ms
              });
              
              // 可选：基于VAD结果进行其他操作
              if (message.is_speaking) {
                onSpeechDetected(message);
              } else if (message.silence_timeout) {
                onSilenceTimeout();
              }
              break;
              
            case 'error':
              console.error('WebSocket处理错误:', message.message);
              setConnectionError(message.message);
              break;
          }
        } catch (error) {
          console.error('解析WebSocket消息失败:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket连接错误:', error);
        setConnectionError('连接失败');
      };

      ws.onclose = (event) => {
        console.log('WebSocket连接关闭:', event.code, event.reason);
        setIsConnected(false);
        
        // 自动重连（可选）
        if (!event.wasClean && event.code !== 1000) {
          setTimeout(() => {
            console.log('尝试重新连接WebSocket...');
            connectWebSocket();
          }, 3000);
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
      setConnectionError('无法创建连接');
    }
  };

  const startStreamingRecording = async () => {
    try {
      // 确保WebSocket已连接
      if (!isConnected) {
        setConnectionError('WebSocket未连接');
        return;
      }

      // 请求权限
      const { status } = await ExpoAudioStreamModule.requestPermissionsAsync();
      if (status !== 'granted') {
        setConnectionError('需要麦克风权限');
        return;
      }

      // 清空音频缓冲区
      audioBufferRef.current = [];

      // 配置实时录音
      const config: RecordingConfig = {
        interval: 100,          // 更频繁的回调，用于实时流
        enableProcessing: true,
        sampleRate: 16000,
        channels: 1,
        encoding: 'pcm_16bit',
        
        // 关键：实时音频流回调
        onAudioStream: async (audioData) => {
          await sendAudioToWebSocket(audioData);
        },
        
        compression: {
          enabled: false,  // 不压缩，保持实时性
        },
        
        keepAwake: true,
        showNotification: false,  // 流式处理不显示通知
      };

      await startRecording(config);
      console.log('开始流式录音');
      
    } catch (error) {
      console.error('开始流式录音失败:', error);
      setConnectionError('录音启动失败');
    }
  };

  const sendAudioToWebSocket = async (audioData: any) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      // audioData.buffer 包含Float32Array格式的音频数据
      const audioArray = Array.from(audioData.buffer);
      
      // 发送音频数据到WebSocket
      wsRef.current.send(JSON.stringify({
        type: 'audio',
        data: audioArray
      }));
      
      // 可选：本地缓存音频数据
      audioBufferRef.current.push(audioData.buffer);
      
      // 限制缓冲区大小，避免内存溢出
      if (audioBufferRef.current.length > 100) {
        audioBufferRef.current.shift();
      }
      
    } catch (error) {
      console.error('发送音频数据失败:', error);
    }
  };

  const stopStreamingRecording = async () => {
    try {
      await stopRecording();
      
      // 发送结束信号
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
      }
      
      console.log('停止流式录音');
      
    } catch (error) {
      console.error('停止流式录音失败:', error);
    }
  };

  const onSpeechDetected = (vadResult: any) => {
    console.log(`检测到语音 (置信度: ${vadResult.probability.toFixed(3)})`);
    // 在这里可以添加语音检测后的逻辑
    // 例如：开始语音识别、触发UI反馈等
  };

  const onSilenceTimeout = () => {
    console.log('静音超时，可能语音结束');
    // 在这里可以添加静音超时后的逻辑
    // 例如：结束语音识别、保存当前段落等
  };

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close(1000, '用户手动断开');
      wsRef.current = null;
    }
  };

  useEffect(() => {
    connectWebSocket();
    
    return () => {
      disconnectWebSocket();
    };
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>实时VAD流式处理</Text>
      
      {/* WebSocket连接状态 */}
      <View style={styles.statusContainer}>
        <Text style={styles.statusText}>
          WebSocket: {isConnected ? '✅ 已连接' : '❌ 未连接'}
        </Text>
        {connectionError && (
          <Text style={[styles.statusText, styles.errorText]}>
            错误: {connectionError}
          </Text>
        )}
      </View>
      
      {/* VAD结果显示 */}
      {vadResult && isConnected && (
        <View style={styles.vadContainer}>
          <Text style={styles.vadTitle}>实时VAD检测结果</Text>
          <Text style={styles.vadText}>
            状态: <Text style={styles.vadValue}>{vadResult.current_state}</Text>
          </Text>
          <Text style={styles.vadText}>
            是否说话: <Text style={styles.vadValue}>
              {vadResult.is_speaking ? '🗣️ 是' : '🤫 否'}
            </Text>
          </Text>
          <Text style={styles.vadText}>
            置信度: <Text style={styles.vadValue}>
              {vadResult.probability.toFixed(3)}
            </Text>
          </Text>
          <Text style={styles.vadText}>
            处理时间: <Text style={styles.vadValue}>
              {vadResult.processing_time_ms}ms
            </Text>
          </Text>
        </View>
      )}

      {/* 录音状态显示 */}
      {isRecording && (
        <View style={styles.recordingContainer}>
          <Text style={styles.recordingText}>
            🔴 正在录音: {(durationMs / 1000).toFixed(1)}秒
          </Text>
          <Text style={styles.recordingText}>
            缓冲区: {audioBufferRef.current.length} 块
          </Text>
        </View>
      )}

      {/* 控制按钮 */}
      <View style={styles.buttonContainer}>
        {!isConnected && (
          <TouchableOpacity
            style={[styles.button, styles.connectButton]}
            onPress={connectWebSocket}
          >
            <Text style={styles.buttonText}>重新连接</Text>
          </TouchableOpacity>
        )}
        
        <TouchableOpacity
          style={[
            styles.button,
            isRecording ? styles.stopButton : styles.startButton
          ]}
          onPress={isRecording ? stopStreamingRecording : startStreamingRecording}
          disabled={!isConnected}
        >
          <Text style={styles.buttonText}>
            {isRecording ? '停止流式录音' : '开始流式录音'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#f5f5f5',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 20,
    color: '#333',
  },
  statusContainer: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  statusText: {
    fontSize: 16,
    color: '#666',
    marginBottom: 5,
  },
  errorText: {
    color: '#FF3B30',
    fontWeight: 'bold',
  },
  vadContainer: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 15,
    borderLeftWidth: 4,
    borderLeftColor: '#007AFF',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  vadTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 10,
  },
  vadText: {
    fontSize: 16,
    color: '#666',
    marginBottom: 5,
  },
  vadValue: {
    fontWeight: 'bold',
    color: '#333',
  },
  recordingContainer: {
    backgroundColor: '#FFE5E5',
    padding: 15,
    borderRadius: 10,
    marginBottom: 15,
    borderLeftWidth: 4,
    borderLeftColor: '#FF3B30',
  },
  recordingText: {
    fontSize: 16,
    color: '#FF3B30',
    fontWeight: 'bold',
    marginBottom: 5,
  },
  buttonContainer: {
    flexDirection: 'column',
    gap: 10,
  },
  button: {
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  connectButton: {
    backgroundColor: '#FF9500',
  },
  startButton: {
    backgroundColor: '#34C759',
  },
  stopButton: {
    backgroundColor: '#FF3B30',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
```

### 6. 性能对比总结

| 方案 | 延迟 | 数据量 | 性能提升 | 适用场景 |
|------|------|--------|----------|----------|
| **Base64 REST API** | 高 | 133% | 基准 | 兼容性要求高 |
| **高效文件上传** | 中 | 100% | **33%更快** ⚡ | 移动APP推荐 |
| **WebSocket JSON** | 低 | 100% | **130%更快** ⚡ | 实时+调试 |
| **WebSocket二进制** | 最低 | 100% | **228%更快** 🚀 | 实时音频流 |

## 完整的 Expo React Native 集成示例

### 基础录音组件

```typescript
// VoiceRecorderWithAPI.tsx
import React, { useState } from 'react';
import { View, TouchableOpacity, Text, Alert, StyleSheet } from 'react-native';
import { 
  useAudioRecorder, 
  RecordingConfig,
  AudioRecording,
  ExpoAudioStreamModule 
} from '@siteed/expo-audio-studio';
import { useAudioPlayer } from 'expo-audio';
import * as FileSystem from 'expo-file-system';

const API_BASE_URL = 'http://your-api.com';

export function VoiceRecorderWithAPI() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [audioResult, setAudioResult] = useState<AudioRecording | null>(null);
  
  // 使用 expo-audio-studio 的录音 hook
  const {
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    durationMs,
    size,
    isRecording,
    isPaused,
  } = useAudioRecorder();

  // 使用 expo-audio 的播放器
  const player = useAudioPlayer(audioResult?.fileUri ?? "");

  const handleStartRecording = async () => {
    try {
      // 请求权限
      const { status } = await ExpoAudioStreamModule.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('权限错误', '需要麦克风权限才能录音');
        return;
      }

      // 配置录音参数 - 优化用于语音识别
      const config: RecordingConfig = {
        interval: 500,           // 每500ms报告一次状态
        enableProcessing: true,  // 启用音频处理
        sampleRate: 16000,      // 16kHz采样率，适合语音识别
        channels: 1,            // 单声道
        encoding: 'pcm_16bit',  // 16位PCM编码
        
        // 音频压缩配置
        compression: {
          enabled: false,       // 不压缩，保持原始质量
          format: 'aac',
          bitrate: 128000,
        },
        
        // 录音被中断时自动恢复
        autoResumeAfterInterruption: true,
        
        // 保持设备唤醒
        keepAwake: true,
        
        // 显示录音通知
        showNotification: true,
        
        // 可选：实时音频流处理
        onAudioStream: async (audioData) => {
          console.log('实时音频数据:', audioData.buffer.length);
        },
        
        // 可选：录音中断处理
        onRecordingInterrupted: (event) => {
          console.log('录音被中断:', event.reason);
        },
      };

      await startRecording(config);
    } catch (error) {
      console.error('开始录音失败:', error);
      Alert.alert('错误', '无法开始录音');
    }
  };

  const handleStopRecording = async () => {
    try {
      setIsProcessing(true);
      
      // 停止录音并获取结果
      const result = await stopRecording();
      setAudioResult(result);
      
      if (!result.fileUri) {
        throw new Error('录音文件创建失败');
      }

      console.log('录音完成:', {
        fileUri: result.fileUri,
        duration: durationMs / 1000,
        size: size,
      });

      // 处理录音文件
      await processAudioFile(result.fileUri);

    } catch (error) {
      console.error('停止录音失败:', error);
      Alert.alert('错误', '停止录音失败');
    } finally {
      setIsProcessing(false);
    }
  };

  const processAudioFile = async (fileUri: string) => {
    try {
      // 方法1: 使用优化的文件上传API（推荐）
      await processWithFileUpload(fileUri);
      
      // 方法2: 使用Base64编码（备用）
      // await processWithBase64(fileUri);
      
    } catch (error) {
      console.error('音频处理失败:', error);
      Alert.alert('处理失败', error.message);
    }
  };

  // 推荐方法：直接文件上传，避免Base64编码
  const processWithFileUpload = async (fileUri: string) => {
    const formData = new FormData();
    
    // 准备文件数据
    formData.append('audio', {
      uri: fileUri,
      type: 'audio/wav',  // expo-audio-studio 默认输出WAV格式
      name: 'recording.wav',
    } as any);
    
    formData.append('sample_rate', '16000');
    formData.append('enable_vad', 'true');
    formData.append('return_audio', 'false');  // 只需要VAD结果
    formData.append('output_format', 'json');

    const response = await fetch(`${API_BASE_URL}/api/v1/mobile/process-audio-efficient`, {
      method: 'POST',
      body: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    if (!response.ok) {
      throw new Error(`API请求失败: ${response.status}`);
    }

    const result = await response.json();
    handleProcessingResult(result);
  };

  // 备用方法：Base64编码（兼容性更好）
  const processWithBase64 = async (fileUri: string) => {
    // 读取音频文件
    const audioBase64 = await FileSystem.readAsStringAsync(fileUri, {
      encoding: FileSystem.EncodingType.Base64,
    });

    const response = await fetch(`${API_BASE_URL}/api/v1/mobile/process-audio`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        audio_base64: audioBase64,
        format: 'wav',
        sample_rate: 16000,
        enable_vad: true,
        vad_window_duration: 0.5,
        vad_overlap: 0.1,
        return_format: 'segments',
        compress_output: false,
      }),
    });

    if (!response.ok) {
      throw new Error(`API请求失败: ${response.status}`);
    }

    const result = await response.json();
    handleProcessingResult(result);
  };

  const handleProcessingResult = (result: any) => {
    if (result.success) {
      if (result.has_speech) {
        const speechDuration = result.speech_segments.reduce(
          (sum: number, seg: any) => sum + seg.duration, 0
        ).toFixed(1);
        
        Alert.alert(
          '录音处理成功',
          `✅ 检测到语音！\n` +
          `🎤 语音段数: ${result.speech_segments.length}\n` +
          `⏱️ 语音时长: ${speechDuration}秒\n` +
          `📊 总时长: ${result.total_duration}秒\n` +
          `🔄 处理时间: ${result.processing_time_ms}ms`,
          [
            {
              text: '发送到后端',
              onPress: () => sendToBackend(result),
            },
            { text: '确定', style: 'default' },
          ]
        );
      } else {
        Alert.alert('提示', '❌ 未检测到有效语音，请重新录制');
      }
    } else {
      Alert.alert('处理失败', result.message || '未知错误');
    }
  };

  const sendToBackend = async (vadResult: any) => {
    try {
      // 发送VAD结果到你的后端服务
      const response = await fetch(`${API_BASE_URL}/api/your-backend-endpoint`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          audio_file_uri: audioResult?.fileUri,
          vad_result: vadResult,
          timestamp: Date.now(),
          user_id: 'current_user_id', // 替换为实际用户ID
        }),
      });

      if (response.ok) {
        Alert.alert('成功', '✅ 音频已发送到后端处理');
      } else {
        throw new Error('后端处理失败');
      }
    } catch (error) {
      console.error('发送到后端失败:', error);
      Alert.alert('发送失败', '❌ 无法发送到后端服务器');
    }
  };

  const playRecording = async () => {
    if (player && audioResult?.fileUri) {
      try {
        await player.play();
      } catch (error) {
        console.error('播放失败:', error);
        Alert.alert('播放失败', '无法播放录音');
      }
    }
  };

  const renderRecordingButton = () => {
    if (isProcessing) {
      return (
        <View style={[styles.recordButton, styles.processingButton]}>
          <Text style={styles.buttonText}>处理中...</Text>
        </View>
      );
    }

    if (isRecording) {
      return (
        <TouchableOpacity
          style={[styles.recordButton, styles.recordingButton]}
          onPress={handleStopRecording}
        >
          <Text style={styles.buttonText}>
            停止录音 {(durationMs / 1000).toFixed(1)}s
          </Text>
        </TouchableOpacity>
      );
    }

    if (isPaused) {
      return (
        <View style={styles.pausedContainer}>
          <TouchableOpacity
            style={[styles.recordButton, styles.resumeButton]}
            onPress={resumeRecording}
          >
            <Text style={styles.buttonText}>继续录音</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.recordButton, styles.stopButton]}
            onPress={handleStopRecording}
          >
            <Text style={styles.buttonText}>完成录音</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return (
      <TouchableOpacity
        style={[styles.recordButton, styles.startButton]}
        onPress={handleStartRecording}
      >
        <Text style={styles.buttonText}>开始录音</Text>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>语音录制与VAD检测</Text>
      
      {/* 录音状态显示 */}
      {(isRecording || isPaused) && (
        <View style={styles.statusContainer}>
          <Text style={styles.statusText}>
            📊 时长: {(durationMs / 1000).toFixed(1)}秒
          </Text>
          <Text style={styles.statusText}>
            💾 大小: {(size / 1024).toFixed(1)}KB
          </Text>
          {isRecording && (
            <TouchableOpacity
              style={styles.pauseButton}
              onPress={pauseRecording}
            >
              <Text style={styles.pauseButtonText}>暂停</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* 录音按钮 */}
      {renderRecordingButton()}

      {/* 播放按钮 */}
      {audioResult?.fileUri && !isRecording && !isPaused && (
        <TouchableOpacity
          style={[styles.recordButton, styles.playButton]}
          onPress={playRecording}
        >
          <Text style={styles.buttonText}>播放录音</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

// 样式定义
const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#f5f5f5',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 30,
    color: '#333',
  },
  statusContainer: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statusText: {
    fontSize: 16,
    marginVertical: 2,
    color: '#666',
  },
  recordButton: {
    width: 120,
    height: 120,
    borderRadius: 60,
    justifyContent: 'center',
    alignItems: 'center',
    marginVertical: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 5,
  },
  startButton: {
    backgroundColor: '#007AFF',
  },
  recordingButton: {
    backgroundColor: '#FF3B30',
  },
  processingButton: {
    backgroundColor: '#FF9500',
  },
  stopButton: {
    backgroundColor: '#FF3B30',
  },
  resumeButton: {
    backgroundColor: '#34C759',
  },
  playButton: {
    backgroundColor: '#5856D6',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  pausedContainer: {
    flexDirection: 'row',
    gap: 15,
  },
  pauseButton: {
    backgroundColor: '#FF9500',
    paddingHorizontal: 15,
    paddingVertical: 5,
    borderRadius: 15,
    marginTop: 10,
  },
  pauseButtonText: {
    color: 'white',
    fontSize: 12,
    fontWeight: 'bold',
  },
});
```

## 性能优化建议

### 1. 音频压缩

如果音频文件较大，可以启用压缩：

```javascript
{
  return_format: 'base64',
  compress_output: true,  // 将使用 FLAC 格式压缩
}
```

### 2. 缓存策略

对于重复的音频，可以在客户端实现缓存：

```javascript
import AsyncStorage from '@react-native-async-storage/async-storage';

const cacheKey = `audio_${audioHash}`;
const cached = await AsyncStorage.getItem(cacheKey);

if (cached) {
  return JSON.parse(cached);
} else {
  const result = await processAudio(audioBase64);
  await AsyncStorage.setItem(cacheKey, JSON.stringify(result));
  return result;
}
```

### 3. 分块处理

对于长音频，可以分块处理：

```javascript
const CHUNK_DURATION = 30; // 30秒一块

// 将音频分割成多个块
const chunks = splitAudioIntoChunks(audioBase64, CHUNK_DURATION);

// 批量处理
const formData = new FormData();
chunks.forEach((chunk, i) => {
  formData.append('audio_files', new Blob([chunk]), `chunk_${i}.m4a`);
});

const response = await fetch('/api/v1/mobile/batch-process', {
  method: 'POST',
  body: formData,
});
```

## 错误处理

```javascript
try {
  const response = await processAudio(audioBase64);
  // 处理成功
} catch (error) {
  if (error.response) {
    // 服务器返回错误
    switch (error.response.status) {
      case 400:
        Alert.alert('格式错误', '音频格式不支持');
        break;
      case 413:
        Alert.alert('文件太大', '请录制更短的音频');
        break;
      case 500:
        Alert.alert('服务器错误', '请稍后重试');
        break;
    }
  } else {
    // 网络错误
    Alert.alert('网络错误', '请检查网络连接');
  }
}
```

## 最佳实践

### 1. 录音配置优化
- **采样率**：使用 16kHz，平衡质量与性能
- **声道**：单声道，减少50%数据量
- **格式选择**：
  - 批量处理：优先 WAV > FLAC > OGG
  - 实时流：Float32 PCM（WebSocket二进制）
  - 移动端：M4A（Expo默认）→ 服务端自动转换

### 2. API 选择策略

#### 移动APP场景
```javascript
// 推荐：高效文件上传（性能提升33%）
const uploadWithFormData = async (audioUri) => {
  const formData = new FormData();
  formData.append('audio', {
    uri: audioUri,
    type: 'audio/wav',
    name: 'recording.wav'
  });
  
  return fetch('/api/v1/mobile/process-audio-efficient', {
    method: 'POST',
    body: formData
  });
};
```

#### 实时语音场景
```javascript
// 推荐：WebSocket二进制流（性能提升228%）
const streamProcessor = new BinaryStreamVADProcessor(
  'ws://api.com/api/v1/stream/vad-binary'
);

// 实时处理音频块
microphoneStream.on('data', (audioChunk) => {
  streamProcessor.sendAudioBinary(audioChunk);
});
```

#### 批量分析场景
```javascript
// 推荐：批量处理API
const formData = new FormData();
audioFiles.forEach(file => formData.append('audio_files', file));
formData.append('merge_results', 'true');

fetch('/api/v1/mobile/batch-process', {
  method: 'POST',
  body: formData
});
```

### 3. WebSocket最佳实践

#### 连接管理
```javascript
class RobustWebSocketVAD {
  constructor(url) {
    this.url = url;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // 指数退避
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);
    
    this.ws.onopen = () => {
      console.log('WebSocket连接成功');
      this.reconnectAttempts = 0;
      this.sendConfig();
    };

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++;
          this.reconnectDelay *= 2; // 指数退避
          this.connect();
        }, this.reconnectDelay);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };
  }

  sendConfig() {
    this.ws.send(JSON.stringify({
      sample_rate: 16000,
      window_size: 1024
    }));
  }
}
```

#### 音频缓冲管理
```javascript
class AudioBufferManager {
  constructor(bufferSize = 4096) {
    this.buffer = new Float32Array(bufferSize);
    this.writePos = 0;
    this.readPos = 0;
  }

  write(audioData) {
    // 环形缓冲区实现
    for (let i = 0; i < audioData.length; i++) {
      this.buffer[this.writePos] = audioData[i];
      this.writePos = (this.writePos + 1) % this.buffer.length;
    }
  }

  read(size) {
    const result = new Float32Array(size);
    for (let i = 0; i < size; i++) {
      result[i] = this.buffer[this.readPos];
      this.readPos = (this.readPos + 1) % this.buffer.length;
    }
    return result;
  }
}
```

### 4. VAD 参数调优

#### 不同场景的参数建议
```javascript
// 会议录音（多人对话）
const meetingConfig = {
  vad_window_duration: 0.3,  // 短窗口，快速响应
  vad_overlap: 0.1,          // 小重叠，减少延迟
  threshold: 0.3             // 较低阈值，捕获轻声
};

// 语音助手（单人清晰语音）
const assistantConfig = {
  vad_window_duration: 0.5,  // 标准窗口
  vad_overlap: 0.2,          // 适中重叠
  threshold: 0.5             // 标准阈值
};

// 嘈杂环境（噪音过滤）
const noisyConfig = {
  vad_window_duration: 0.8,  // 长窗口，稳定判断
  vad_overlap: 0.3,          // 大重叠，提高准确性
  threshold: 0.7             // 高阈值，过滤噪音
};
```

### 5. 错误处理与恢复

#### HTTP API错误处理
```javascript
const apiCall = async (url, data, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        body: data,
        timeout: 30000 // 30秒超时
      });

      if (response.ok) {
        return await response.json();
      }

      // HTTP错误处理
      switch (response.status) {
        case 413: // 文件过大
          throw new Error('音频文件过大，请录制更短的音频');
        case 429: // 请求过频
          await sleep(1000 * (i + 1)); // 退避等待
          continue;
        case 500: // 服务器错误
          if (i === retries - 1) throw new Error('服务器暂时不可用');
          continue;
        default:
          throw new Error(`API错误: ${response.status}`);
      }
    } catch (error) {
      if (i === retries - 1) throw error;
      await sleep(1000 * (i + 1));
    }
  }
};
```

#### WebSocket错误恢复
```javascript
class ResilientsWebSocket {
  constructor(url) {
    this.url = url;
    this.messageQueue = [];
    this.isConnected = false;
    this.connect();
  }

  send(message) {
    if (this.isConnected) {
      this.ws.send(message);
    } else {
      // 排队等待重连
      this.messageQueue.push(message);
    }
  }

  onReconnect() {
    // 重发排队的消息
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      this.ws.send(message);
    }
  }
}
```

### 6. 性能监控与优化

#### 性能指标收集
```javascript
class PerformanceMonitor {
  constructor() {
    this.metrics = {
      apiCalls: 0,
      totalProcessingTime: 0,
      errors: 0,
      reconnections: 0
    };
  }

  recordAPICall(duration, success) {
    this.metrics.apiCalls++;
    this.metrics.totalProcessingTime += duration;
    if (!success) this.metrics.errors++;
  }

  getAverageProcessingTime() {
    return this.metrics.totalProcessingTime / this.metrics.apiCalls;
  }

  getErrorRate() {
    return this.metrics.errors / this.metrics.apiCalls;
  }
}
```

### 7. 资源管理

#### 内存优化
```javascript
// 及时清理大对象
const processAudio = async (audioData) => {
  try {
    const response = await apiCall(audioData);
    return response;
  } finally {
    // 清理内存
    audioData = null;
    if (global.gc) global.gc(); // Node.js环境
  }
};

// 流式处理避免内存累积
const processAudioStream = async function* (audioStream) {
  for await (const chunk of audioStream) {
    const result = await processChunk(chunk);
    yield result;
    // chunk会被垃圾回收
  }
};
```

### 8. 用户体验优化

#### 进度反馈
```javascript
const processWithProgress = async (audioFile, onProgress) => {
  const steps = [
    { name: '上传音频', weight: 30 },
    { name: '格式转换', weight: 20 },
    { name: 'VAD分析', weight: 40 },
    { name: '结果生成', weight: 10 }
  ];

  let progress = 0;
  for (const step of steps) {
    onProgress({ current: step.name, progress });
    await performStep(step);
    progress += step.weight;
    onProgress({ current: step.name, progress });
  }
};
```

### 9. 调试与测试

#### API调试工具
```javascript
const debugAPI = {
  logRequest: (url, data) => {
    console.log(`[API] ${url}`, {
      size: data instanceof FormData ? 'FormData' : JSON.stringify(data).length,
      timestamp: new Date().toISOString()
    });
  },

  logResponse: (response, duration) => {
    console.log(`[API] Response`, {
      status: response.status,
      duration: `${duration}ms`,
      timestamp: new Date().toISOString()
    });
  }
};
```

### 10. 部署检查清单

- ✅ **FFmpeg安装**: 支持多种音频格式
- ✅ **TEN-VAD配置**: 确保高质量VAD检测
- ✅ **WebSocket支持**: 代理服务器配置正确
- ✅ **文件大小限制**: 设置合理的上传限制
- ✅ **CORS配置**: 允许跨域请求
- ✅ **SSL证书**: WebSocket需要WSS连接
- ✅ **监控告警**: API响应时间和错误率监控

## 服务端要求

确保安装必要的依赖：

```bash
pip install soundfile numpy
# 如果需要支持 mp3, m4a 等格式
# Ubuntu/Debian: apt-get install ffmpeg
# macOS: brew install ffmpeg
```

## 快速参考

### API端点速览

| 端点 | 方法 | 用途 | 性能 | 推荐场景 |
|------|------|------|------|----------|
| `/api/v1/mobile/process-audio` | POST | Base64音频处理 | 基准 | 兼容性优先 |
| `/api/v1/mobile/process-audio-efficient` | POST | 直接文件上传 | **+33%** ⚡ | **移动APP推荐** |
| `/api/v1/mobile/quick-vad` | POST | 快速VAD检测 | **+50%** ⚡ | 预检测 |
| `/api/v1/mobile/batch-process` | POST | 批量处理 | **+25%** ⚡ | 多文件处理 |
| `/api/v1/stream/vad` | WebSocket | JSON流式VAD | **+130%** ⚡ | 实时+调试 |
| `/api/v1/stream/vad-binary` | WebSocket | 二进制流式VAD | **+228%** 🚀 | **实时音频流** |

### WebSocket连接示例

```javascript
// 快速连接WebSocket VAD
const ws = new WebSocket('ws://localhost:8000/api/v1/stream/vad');

ws.onopen = () => {
  // 发送配置
  ws.send(JSON.stringify({
    type: 'config',
    sample_rate: 16000,
    channels: 1
  }));
};

ws.onmessage = (event) => {
  const result = JSON.parse(event.data);
  if (result.type === 'vad') {
    console.log('是否说话:', result.is_speaking);
    console.log('置信度:', result.probability);
  }
};

// 发送音频数据
ws.send(JSON.stringify({
  type: 'audio',
  data: audioFloatArray
}));

// 结束处理
ws.send(JSON.stringify({type: 'end'}));
```

### React Native快速集成

```typescript
// 1. 安装依赖
npm install expo-av expo-file-system

// 2. 录音并处理
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';

const recording = new Audio.Recording();
await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
await recording.startAsync();

// 录音完成后
await recording.stopAndUnloadAsync();
const uri = recording.getURI();

// 使用高效API处理
const formData = new FormData();
formData.append('audio', {
  uri: uri,
  type: 'audio/m4a',
  name: 'recording.m4a'
});

const response = await fetch('/api/v1/mobile/process-audio-efficient', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log('VAD结果:', result.has_speech);
```

### 状态检查命令

```bash
# 检查API健康状态
curl http://localhost:8000/api/v1/mobile/health

# 检查WebSocket流状态
curl http://localhost:8000/api/v1/stream/status

# 测试快速VAD
curl -X POST http://localhost:8000/api/v1/mobile/quick-vad-file \
  -F "audio=@test.wav" \
  -F "sample_rate=16000"
```

### 故障排除

| 问题 | 解决方案 |
|------|----------|
| `TEN-VAD not available` | 检查TEN-VAD库路径和权限 |
| `Format not recognised` | 安装FFmpeg支持更多格式 |
| `WebSocket connection failed` | 检查防火墙和代理设置 |
| `413 Request Entity Too Large` | 减小文件大小或调整服务器限制 |
| `高延迟` | 使用WebSocket二进制流或高效API |

---

📚 **更多文档**:
- [Swagger UI测试指南](./swagger-testing-guide.md)
- [音频传输优化方案](./audio-transmission-optimization.md)
- [FFmpeg安装指南](./ffmpeg-installation.md)