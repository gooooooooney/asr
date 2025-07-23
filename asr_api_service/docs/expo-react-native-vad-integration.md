# Expo React Native 语音录制与VAD检测集成指南

## 目录
1. [概述](#概述)
2. [技术架构](#技术架构)
3. [环境准备](#环境准备)
4. [实现方案](#实现方案)
5. [代码实现](#代码实现)
6. [优化策略](#优化策略)
7. [常见问题](#常见问题)
8. [最佳实践](#最佳实践)

## 概述

本文档详细说明如何在 Expo React Native 应用中实现以下功能流程：

1. **录制音频**：使用 expo-audio 录制用户语音
2. **VAD检测**：将音频发送到 VAD API 检测有效语音段
3. **发送音频**：将检测后的有效音频发送到后端服务器

### 技术挑战

- **音频格式转换**：Expo Audio 录制的格式与 API 所需格式的转换
- **实时性要求**：平衡实时检测与性能开销
- **网络传输**：优化音频数据的传输效率
- **用户体验**：提供流畅的录音和反馈体验

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                   Expo React Native App                  │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ Audio Input │ -> │ Audio Buffer │ -> │ Processor │ │
│  └─────────────┘    └──────────────┘    └───────────┘ │
│         │                                       │        │
│         v                                       v        │
│  ┌─────────────┐                        ┌───────────┐  │
│  │ expo-audio  │                        │ VAD Check │  │
│  └─────────────┘                        └───────────┘  │
│                                                │        │
└────────────────────────────────────────────────┼────────┘
                                                 │
                                                 v
                                        ┌────────────────┐
                                        │   VAD API      │
                                        └────────────────┘
                                                 │
                                                 v
                                        ┌────────────────┐
                                        │ Backend Server │
                                        └────────────────┘
```

## 环境准备

### 1. 安装依赖

```bash
# 安装 expo-audio
expo install expo-audio

# 安装其他必要依赖
npm install axios buffer base64-arraybuffer
```

### 2. 权限配置

在 `app.json` 中添加音频权限：

```json
{
  "expo": {
    "ios": {
      "infoPlist": {
        "NSMicrophoneUsageDescription": "This app uses the microphone to record audio for speech recognition."
      }
    },
    "android": {
      "permissions": ["RECORD_AUDIO"]
    }
  }
}
```

## 实现方案

### 方案一：完整录制后检测（推荐初期使用）

**优点**：
- 实现简单
- 音频质量完整
- 易于调试

**缺点**：
- 响应延迟较高
- 用户需要等待录制完成

**流程**：
1. 用户按住按钮开始录制
2. 松开按钮停止录制
3. 将完整音频发送到 VAD API
4. 提取有效音频段
5. 发送到后端

### 方案二：实时流式检测（进阶方案）

**优点**：
- 实时响应
- 更好的用户体验
- 可以实时显示语音活动状态

**缺点**：
- 实现复杂
- 需要处理音频流分块
- 对网络要求较高

**流程**：
1. 开始录制并创建音频流
2. 定期（如每100ms）读取音频块
3. 实时发送到 VAD API 检测
4. 累积有效音频段
5. 结束时发送完整有效音频

## 代码实现

### 1. 音频录制管理器

```typescript
// AudioRecorder.ts
import { Audio } from 'expo-audio';
import * as FileSystem from 'expo-file-system';

export interface AudioConfig {
  android: {
    extension: '.wav',
    outputFormat: Audio.AndroidOutputFormat.DEFAULT,
    audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 128000,
  };
  ios: {
    extension: '.wav',
    audioQuality: Audio.IOSAudioQuality.HIGH,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 128000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  };
  web: {
    mimeType: 'audio/wav',
    bitsPerSecond: 128000,
  };
}

export class AudioRecorder {
  private recording: Audio.Recording | null = null;
  private recordingUri: string | null = null;
  
  constructor() {
    this.setupAudio();
  }
  
  private async setupAudio() {
    try {
      // 请求权限
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        throw new Error('音频录制权限被拒绝');
      }
      
      // 设置音频模式
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        shouldDuckAndroid: true,
        staysActiveInBackground: false,
        playThroughEarpieceAndroid: false,
      });
    } catch (error) {
      console.error('音频设置失败:', error);
      throw error;
    }
  }
  
  async startRecording(): Promise<void> {
    try {
      // 停止任何现有录音
      if (this.recording) {
        await this.stopRecording();
      }
      
      // 创建录音配置
      const recordingOptions: Audio.RecordingOptions = {
        android: {
          extension: '.wav',
          outputFormat: Audio.AndroidOutputFormat.DEFAULT,
          audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
        },
        ios: {
          extension: '.wav',
          audioQuality: Audio.IOSAudioQuality.HIGH,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
          linearPCMBitDepth: 16,
          linearPCMIsBigEndian: false,
          linearPCMIsFloat: false,
        },
        web: {
          mimeType: 'audio/wav',
          bitsPerSecond: 128000,
        },
      };
      
      // 创建并开始录音
      const { recording } = await Audio.Recording.createAsync(
        recordingOptions,
        this.onRecordingStatusUpdate.bind(this)
      );
      
      this.recording = recording;
      console.log('录音开始');
    } catch (error) {
      console.error('开始录音失败:', error);
      throw error;
    }
  }
  
  async stopRecording(): Promise<string | null> {
    if (!this.recording) {
      return null;
    }
    
    try {
      console.log('停止录音...');
      await this.recording.stopAndUnloadAsync();
      const uri = this.recording.getURI();
      this.recording = null;
      this.recordingUri = uri;
      
      console.log('录音已保存到:', uri);
      return uri;
    } catch (error) {
      console.error('停止录音失败:', error);
      throw error;
    }
  }
  
  private onRecordingStatusUpdate(status: Audio.RecordingStatus) {
    if (status.isRecording) {
      console.log('录音中...', status.durationMillis);
    }
  }
  
  async getRecordingUri(): Promise<string | null> {
    return this.recordingUri;
  }
}
```

### 2. 音频处理工具

```typescript
// AudioProcessor.ts
import * as FileSystem from 'expo-file-system';
import { Buffer } from 'buffer';
import { decode } from 'base64-arraybuffer';

export class AudioProcessor {
  /**
   * 读取音频文件并转换为浮点数组
   */
  static async audioFileToFloatArray(uri: string): Promise<Float32Array> {
    try {
      // 读取文件为 base64
      const base64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });
      
      // 转换为 ArrayBuffer
      const arrayBuffer = decode(base64);
      
      // WAV 文件处理
      const audioData = await this.parseWAVFile(arrayBuffer);
      return audioData;
    } catch (error) {
      console.error('音频文件转换失败:', error);
      throw error;
    }
  }
  
  /**
   * 解析 WAV 文件格式
   */
  private static async parseWAVFile(arrayBuffer: ArrayBuffer): Promise<Float32Array> {
    const dataView = new DataView(arrayBuffer);
    
    // 检查 WAV 文件头
    const riff = String.fromCharCode(
      dataView.getUint8(0),
      dataView.getUint8(1),
      dataView.getUint8(2),
      dataView.getUint8(3)
    );
    
    if (riff !== 'RIFF') {
      throw new Error('不是有效的 WAV 文件');
    }
    
    // 跳过文件头，找到 data 块
    let offset = 12; // 跳过 RIFF header
    while (offset < dataView.byteLength - 8) {
      const chunkId = String.fromCharCode(
        dataView.getUint8(offset),
        dataView.getUint8(offset + 1),
        dataView.getUint8(offset + 2),
        dataView.getUint8(offset + 3)
      );
      
      const chunkSize = dataView.getUint32(offset + 4, true);
      
      if (chunkId === 'data') {
        // 找到音频数据
        offset += 8;
        break;
      }
      
      offset += 8 + chunkSize;
    }
    
    // 读取音频数据（假设是 16-bit PCM）
    const audioDataLength = (dataView.byteLength - offset) / 2;
    const audioData = new Float32Array(audioDataLength);
    
    for (let i = 0; i < audioDataLength; i++) {
      // 读取 16-bit 样本并归一化到 [-1, 1]
      const sample = dataView.getInt16(offset + i * 2, true);
      audioData[i] = sample / 32768.0;
    }
    
    return audioData;
  }
  
  /**
   * 将浮点数组分块
   */
  static chunkAudioData(
    audioData: Float32Array,
    chunkSize: number
  ): Float32Array[] {
    const chunks: Float32Array[] = [];
    
    for (let i = 0; i < audioData.length; i += chunkSize) {
      const chunk = audioData.slice(i, i + chunkSize);
      chunks.push(chunk);
    }
    
    return chunks;
  }
  
  /**
   * 合并音频块
   */
  static mergeAudioChunks(chunks: Float32Array[]): Float32Array {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const merged = new Float32Array(totalLength);
    
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    
    return merged;
  }
  
  /**
   * 提取有效音频段
   */
  static extractValidSegments(
    audioData: Float32Array,
    segments: Array<{ start: number; end: number }>,
    sampleRate: number
  ): Float32Array {
    const validChunks: Float32Array[] = [];
    
    for (const segment of segments) {
      const startSample = Math.floor(segment.start * sampleRate);
      const endSample = Math.floor(segment.end * sampleRate);
      
      const chunk = audioData.slice(startSample, endSample);
      validChunks.push(chunk);
    }
    
    return this.mergeAudioChunks(validChunks);
  }
}
```

### 3. VAD API 客户端

```typescript
// VADClient.ts
import axios from 'axios';

export interface VADDetectionResult {
  is_speaking: boolean;
  state: 'speech' | 'silence';
  state_changed: boolean;
  probability: number;
  rms: number;
  max_amplitude: number;
  silence_timeout: boolean;
  processing_time_ms: number;
}

export interface VADFileAnalysisResult {
  speech_segments: Array<{
    start: number;
    end: number;
    duration: number;
  }>;
  statistics: {
    total_duration: number;
    total_speech_duration: number;
    total_silence_duration: number;
    speech_ratio: number;
    segment_count: number;
    average_segment_duration: number;
  };
}

export class VADClient {
  private baseURL: string;
  
  constructor(baseURL: string = 'http://localhost:8000') {
    this.baseURL = baseURL;
  }
  
  /**
   * 检测单个音频块
   */
  async detectVoiceActivity(
    audioData: number[],
    sampleRate: number = 16000
  ): Promise<VADDetectionResult> {
    try {
      const response = await axios.post(
        `${this.baseURL}/api/v1/vad/detect`,
        {
          audio_data: audioData,
          sample_rate: sampleRate,
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('VAD 检测失败:', error);
      throw error;
    }
  }
  
  /**
   * 分析完整音频文件
   */
  async analyzeAudioFile(
    audioData: number[],
    sampleRate: number = 16000,
    windowDuration: number = 0.5,
    overlap: number = 0.1
  ): Promise<VADFileAnalysisResult> {
    try {
      const response = await axios.post(
        `${this.baseURL}/api/v1/vad/analyze-file`,
        {
          audio_data: audioData,
          sample_rate: sampleRate,
          window_duration: windowDuration,
          overlap: overlap,
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('音频文件分析失败:', error);
      throw error;
    }
  }
  
  /**
   * 批量处理音频片段
   */
  async processSegments(
    segments: number[][],
    sampleRate: number = 16000,
    resetBetweenSegments: boolean = false
  ) {
    try {
      const response = await axios.post(
        `${this.baseURL}/api/v1/vad/process-segments`,
        {
          segments: segments,
          sample_rate: sampleRate,
          reset_between_segments: resetBetweenSegments,
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('批量处理失败:', error);
      throw error;
    }
  }
}
```

### 4. 主要组件实现

```typescript
// VoiceRecorder.tsx
import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { AudioRecorder } from './AudioRecorder';
import { AudioProcessor } from './AudioProcessor';
import { VADClient } from './VADClient';
import axios from 'axios';

interface VoiceRecorderProps {
  vadApiUrl: string;
  backendApiUrl: string;
  onRecordingComplete?: (audioData: Float32Array) => void;
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  vadApiUrl,
  backendApiUrl,
  onRecordingComplete,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [vadStatus, setVadStatus] = useState<string>('');
  
  const audioRecorder = useRef(new AudioRecorder());
  const vadClient = useRef(new VADClient(vadApiUrl));
  
  const startRecording = async () => {
    try {
      setIsRecording(true);
      setVadStatus('录音中...');
      await audioRecorder.current.startRecording();
    } catch (error) {
      console.error('开始录音失败:', error);
      Alert.alert('错误', '无法开始录音');
      setIsRecording(false);
    }
  };
  
  const stopRecording = async () => {
    try {
      setIsRecording(false);
      setIsProcessing(true);
      setVadStatus('处理中...');
      
      // 停止录音
      const audioUri = await audioRecorder.current.stopRecording();
      if (!audioUri) {
        throw new Error('没有录音数据');
      }
      
      // 转换音频格式
      const audioData = await AudioProcessor.audioFileToFloatArray(audioUri);
      console.log('音频数据长度:', audioData.length);
      
      // VAD 分析
      setVadStatus('分析语音...');
      const vadResult = await vadClient.current.analyzeAudioFile(
        Array.from(audioData),
        16000
      );
      
      console.log('VAD 分析结果:', vadResult);
      
      // 检查是否有有效语音
      if (vadResult.speech_segments.length === 0) {
        Alert.alert('提示', '未检测到有效语音');
        setIsProcessing(false);
        setVadStatus('');
        return;
      }
      
      // 提取有效音频段
      setVadStatus('提取有效语音...');
      const validAudio = AudioProcessor.extractValidSegments(
        audioData,
        vadResult.speech_segments,
        16000
      );
      
      console.log('有效音频长度:', validAudio.length);
      
      // 发送到后端
      setVadStatus('发送到服务器...');
      await sendAudioToBackend(validAudio);
      
      // 回调
      if (onRecordingComplete) {
        onRecordingComplete(validAudio);
      }
      
      setVadStatus('完成！');
      setTimeout(() => setVadStatus(''), 2000);
      
    } catch (error) {
      console.error('处理录音失败:', error);
      Alert.alert('错误', '处理录音失败');
      setVadStatus('');
    } finally {
      setIsProcessing(false);
    }
  };
  
  const sendAudioToBackend = async (audioData: Float32Array) => {
    try {
      // 方案1：发送原始浮点数组
      const response = await axios.post(`${backendApiUrl}/api/audio/upload`, {
        audio_data: Array.from(audioData),
        sample_rate: 16000,
        format: 'float32',
      });
      
      // 方案2：转换为 WAV 格式发送
      // const wavBlob = await AudioProcessor.floatArrayToWAV(audioData, 16000);
      // const formData = new FormData();
      // formData.append('audio', wavBlob, 'recording.wav');
      // const response = await axios.post(`${backendApiUrl}/api/audio/upload`, formData);
      
      console.log('上传成功:', response.data);
    } catch (error) {
      console.error('上传失败:', error);
      throw error;
    }
  };
  
  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={[
          styles.recordButton,
          isRecording && styles.recordingButton,
          isProcessing && styles.processingButton,
        ]}
        onPressIn={startRecording}
        onPressOut={stopRecording}
        disabled={isProcessing}
      >
        {isProcessing ? (
          <ActivityIndicator color="white" size="large" />
        ) : (
          <Text style={styles.buttonText}>
            {isRecording ? '松开停止' : '按住说话'}
          </Text>
        )}
      </TouchableOpacity>
      
      {vadStatus ? (
        <Text style={styles.statusText}>{vadStatus}</Text>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  recordButton: {
    width: 150,
    height: 150,
    borderRadius: 75,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  recordingButton: {
    backgroundColor: '#FF3B30',
    transform: [{ scale: 1.1 }],
  },
  processingButton: {
    backgroundColor: '#8E8E93',
  },
  buttonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  statusText: {
    marginTop: 20,
    fontSize: 16,
    color: '#666',
  },
});
```

### 5. 实时流式处理（高级）

```typescript
// StreamingVoiceRecorder.tsx
import React, { useState, useRef, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Audio } from 'expo-audio';
import { VADClient } from './VADClient';

export const StreamingVoiceRecorder: React.FC = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechSegments, setSpeechSegments] = useState<number[][]>([]);
  
  const recording = useRef<Audio.Recording | null>(null);
  const vadClient = useRef(new VADClient());
  const audioBuffer = useRef<number[]>([]);
  const processingInterval = useRef<NodeJS.Timeout | null>(null);
  
  const CHUNK_DURATION_MS = 100; // 100ms 块
  const SAMPLE_RATE = 16000;
  const CHUNK_SIZE = (SAMPLE_RATE * CHUNK_DURATION_MS) / 1000;
  
  const startStreamingRecording = async () => {
    try {
      // 配置音频会话
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      
      // 创建录音实例
      const { recording: rec, status } = await Audio.Recording.createAsync(
        {
          android: {
            extension: '.wav',
            outputFormat: Audio.AndroidOutputFormat.PCM_16BIT,
            audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
            sampleRate: SAMPLE_RATE,
            numberOfChannels: 1,
            bitRate: 128000,
          },
          ios: {
            extension: '.wav',
            audioQuality: Audio.IOSAudioQuality.HIGH,
            sampleRate: SAMPLE_RATE,
            numberOfChannels: 1,
            bitRate: 128000,
            linearPCMBitDepth: 16,
            linearPCMIsBigEndian: false,
            linearPCMIsFloat: false,
          },
          web: {
            mimeType: 'audio/wav',
            bitsPerSecond: 128000,
          },
        },
        // 状态更新回调
        (status) => {
          if (status.isRecording) {
            // 可以在这里获取实时音频数据（如果 Expo 支持）
            // 目前 Expo 不支持实时音频流，需要使用定期读取的方式
          }
        },
        // 音频数据回调（如果支持）
        CHUNK_DURATION_MS
      );
      
      recording.current = rec;
      setIsRecording(true);
      
      // 开始定期处理音频
      startProcessingLoop();
      
    } catch (error) {
      console.error('开始流式录音失败:', error);
    }
  };
  
  const startProcessingLoop = () => {
    processingInterval.current = setInterval(async () => {
      await processAudioChunk();
    }, CHUNK_DURATION_MS);
  };
  
  const processAudioChunk = async () => {
    if (!recording.current) return;
    
    try {
      // 注意：Expo Audio 目前不支持实时获取音频数据
      // 这里展示的是理想的实现方式
      // 实际使用时可能需要使用原生模块或等待 Expo 支持
      
      // 模拟获取音频块
      const audioChunk = await getAudioChunk();
      if (!audioChunk || audioChunk.length === 0) return;
      
      // 添加到缓冲区
      audioBuffer.current.push(...audioChunk);
      
      // VAD 检测
      const vadResult = await vadClient.current.detectVoiceActivity(
        audioChunk,
        SAMPLE_RATE
      );
      
      // 更新语音状态
      setIsSpeaking(vadResult.is_speaking);
      
      // 如果状态改变
      if (vadResult.state_changed) {
        if (vadResult.is_speaking) {
          // 开始新的语音段
          console.log('开始说话');
        } else {
          // 结束语音段，保存有效音频
          console.log('停止说话');
          if (audioBuffer.current.length > 0) {
            speechSegments.push([...audioBuffer.current]);
            audioBuffer.current = [];
          }
        }
      }
      
    } catch (error) {
      console.error('处理音频块失败:', error);
    }
  };
  
  const getAudioChunk = async (): Promise<number[]> => {
    // 这是一个模拟实现
    // 实际实现需要从录音缓冲区获取数据
    // Expo 目前不直接支持这个功能
    
    // 可选方案：
    // 1. 使用 expo-av 的自定义原生模块
    // 2. 使用 react-native-audio-recorder-player
    // 3. 等待 Expo 支持实时音频流
    
    return [];
  };
  
  const stopStreamingRecording = async () => {
    if (processingInterval.current) {
      clearInterval(processingInterval.current);
      processingInterval.current = null;
    }
    
    if (recording.current) {
      await recording.current.stopAndUnloadAsync();
      recording.current = null;
    }
    
    setIsRecording(false);
    setIsSpeaking(false);
    
    // 处理收集到的语音段
    if (speechSegments.length > 0) {
      console.log('收集到的语音段:', speechSegments.length);
      // 合并并发送到后端
      await sendCollectedAudio();
    }
  };
  
  const sendCollectedAudio = async () => {
    // 合并所有语音段
    const allAudio = speechSegments.flat();
    // 发送到后端
    // ...
  };
  
  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={[
          styles.recordButton,
          isRecording && styles.recordingButton,
          isSpeaking && styles.speakingButton,
        ]}
        onPress={isRecording ? stopStreamingRecording : startStreamingRecording}
      >
        <Text style={styles.buttonText}>
          {isRecording ? (isSpeaking ? '说话中...' : '聆听中...') : '开始录音'}
        </Text>
      </TouchableOpacity>
      
      <View style={styles.indicator}>
        <View
          style={[
            styles.vadIndicator,
            isSpeaking && styles.vadActive,
          ]}
        />
        <Text style={styles.vadText}>
          {isSpeaking ? '检测到语音' : '静音'}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  recordButton: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  recordingButton: {
    backgroundColor: '#FF9500',
  },
  speakingButton: {
    backgroundColor: '#34C759',
    transform: [{ scale: 1.1 }],
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  indicator: {
    marginTop: 30,
    alignItems: 'center',
  },
  vadIndicator: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#C7C7CC',
    marginBottom: 10,
  },
  vadActive: {
    backgroundColor: '#34C759',
  },
  vadText: {
    fontSize: 14,
    color: '#666',
  },
});
```

## 优化策略

### 1. 音频压缩

```typescript
// AudioCompressor.ts
export class AudioCompressor {
  /**
   * 降采样音频数据
   */
  static downsample(
    audioData: Float32Array,
    fromSampleRate: number,
    toSampleRate: number
  ): Float32Array {
    if (fromSampleRate === toSampleRate) {
      return audioData;
    }
    
    const ratio = fromSampleRate / toSampleRate;
    const newLength = Math.floor(audioData.length / ratio);
    const result = new Float32Array(newLength);
    
    for (let i = 0; i < newLength; i++) {
      const index = Math.floor(i * ratio);
      result[i] = audioData[index];
    }
    
    return result;
  }
  
  /**
   * 音频数据量化压缩
   */
  static quantize(audioData: Float32Array, bits: number = 8): Uint8Array {
    const maxValue = Math.pow(2, bits) - 1;
    const result = new Uint8Array(audioData.length);
    
    for (let i = 0; i < audioData.length; i++) {
      // 归一化到 [0, maxValue]
      const normalized = (audioData[i] + 1) * 0.5 * maxValue;
      result[i] = Math.round(Math.max(0, Math.min(maxValue, normalized)));
    }
    
    return result;
  }
  
  /**
   * 使用 ADPCM 压缩
   */
  static compressADPCM(audioData: Int16Array): Uint8Array {
    // ADPCM 压缩实现
    // 这里需要实现 ADPCM 算法
    // 可以将 16-bit 音频压缩到 4-bit
    return new Uint8Array();
  }
}
```

### 2. 网络优化

```typescript
// NetworkOptimizer.ts
export class NetworkOptimizer {
  private queue: Array<() => Promise<any>> = [];
  private isProcessing = false;
  
  /**
   * 批量发送请求
   */
  async batchRequest(request: () => Promise<any>) {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          const result = await request();
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });
      
      this.processQueue();
    });
  }
  
  private async processQueue() {
    if (this.isProcessing || this.queue.length === 0) {
      return;
    }
    
    this.isProcessing = true;
    
    // 批量处理请求
    const batch = this.queue.splice(0, 5); // 一次处理5个
    
    try {
      await Promise.all(batch.map(req => req()));
    } catch (error) {
      console.error('批量请求失败:', error);
    }
    
    this.isProcessing = false;
    
    // 继续处理剩余请求
    if (this.queue.length > 0) {
      setTimeout(() => this.processQueue(), 100);
    }
  }
  
  /**
   * 使用 WebSocket 进行持久连接
   */
  static createWebSocketConnection(url: string) {
    const ws = new WebSocket(url);
    
    ws.onopen = () => {
      console.log('WebSocket 连接已建立');
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error);
    };
    
    return ws;
  }
}
```

### 3. 缓存策略

```typescript
// AudioCache.ts
import AsyncStorage from '@react-native-async-storage/async-storage';

export class AudioCache {
  private static readonly CACHE_KEY_PREFIX = 'audio_cache_';
  private static readonly MAX_CACHE_SIZE = 10 * 1024 * 1024; // 10MB
  
  /**
   * 缓存音频数据
   */
  static async cacheAudio(key: string, audioData: Float32Array) {
    try {
      const data = Array.from(audioData);
      const jsonData = JSON.stringify(data);
      
      // 检查缓存大小
      const currentSize = await this.getCacheSize();
      if (currentSize + jsonData.length > this.MAX_CACHE_SIZE) {
        await this.clearOldestCache();
      }
      
      await AsyncStorage.setItem(
        `${this.CACHE_KEY_PREFIX}${key}`,
        jsonData
      );
      
      // 记录时间戳
      await AsyncStorage.setItem(
        `${this.CACHE_KEY_PREFIX}${key}_timestamp`,
        Date.now().toString()
      );
    } catch (error) {
      console.error('缓存音频失败:', error);
    }
  }
  
  /**
   * 获取缓存的音频
   */
  static async getCachedAudio(key: string): Promise<Float32Array | null> {
    try {
      const jsonData = await AsyncStorage.getItem(
        `${this.CACHE_KEY_PREFIX}${key}`
      );
      
      if (!jsonData) {
        return null;
      }
      
      const data = JSON.parse(jsonData);
      return new Float32Array(data);
    } catch (error) {
      console.error('获取缓存音频失败:', error);
      return null;
    }
  }
  
  /**
   * 清理最旧的缓存
   */
  private static async clearOldestCache() {
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter(k => k.startsWith(this.CACHE_KEY_PREFIX));
    
    // 获取所有缓存的时间戳
    const timestamps = await Promise.all(
      cacheKeys.map(async (key) => {
        const timestamp = await AsyncStorage.getItem(`${key}_timestamp`);
        return { key, timestamp: parseInt(timestamp || '0') };
      })
    );
    
    // 排序并删除最旧的
    timestamps.sort((a, b) => a.timestamp - b.timestamp);
    if (timestamps.length > 0) {
      await AsyncStorage.removeItem(timestamps[0].key);
      await AsyncStorage.removeItem(`${timestamps[0].key}_timestamp`);
    }
  }
  
  private static async getCacheSize(): Promise<number> {
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter(k => k.startsWith(this.CACHE_KEY_PREFIX));
    
    let totalSize = 0;
    for (const key of cacheKeys) {
      const value = await AsyncStorage.getItem(key);
      if (value) {
        totalSize += value.length;
      }
    }
    
    return totalSize;
  }
}
```

## 常见问题

### 1. 音频格式问题

**问题**：Expo Audio 录制的格式与 VAD API 不兼容

**解决方案**：
```typescript
// 确保录音配置正确
const recordingOptions = {
  android: {
    extension: '.wav',
    outputFormat: Audio.AndroidOutputFormat.PCM_16BIT,
    audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
    sampleRate: 16000,
    numberOfChannels: 1,
  },
  ios: {
    extension: '.wav',
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
    sampleRate: 16000,
    numberOfChannels: 1,
  },
};
```

### 2. 内存问题

**问题**：处理大音频文件时内存溢出

**解决方案**：
- 使用流式处理
- 分块读取和处理
- 及时释放不需要的数据

### 3. 网络延迟

**问题**：VAD API 响应慢

**解决方案**：
- 实现本地 VAD 预检测
- 使用 WebSocket 保持连接
- 批量处理请求

### 4. 权限问题

**问题**：iOS 上录音权限被拒绝

**解决方案**：
```typescript
// 添加友好的权限请求
const requestPermissions = async () => {
  const { status } = await Audio.requestPermissionsAsync();
  
  if (status !== 'granted') {
    Alert.alert(
      '需要麦克风权限',
      '请在设置中允许应用访问麦克风',
      [
        { text: '取消', style: 'cancel' },
        { text: '去设置', onPress: () => Linking.openSettings() },
      ]
    );
    return false;
  }
  
  return true;
};
```

## 最佳实践

### 1. 用户体验

- **视觉反馈**：录音时显示音频波形或音量指示器
- **状态提示**：清晰显示当前状态（录音中、处理中、完成）
- **错误处理**：友好的错误提示和重试机制

### 2. 性能优化

- **防抖处理**：避免频繁的 VAD 请求
- **缓存策略**：缓存最近的 VAD 结果
- **资源管理**：及时释放音频资源

### 3. 安全考虑

- **HTTPS**：生产环境必须使用 HTTPS
- **认证**：API 调用需要认证
- **数据加密**：敏感音频数据应加密传输

### 4. 测试建议

```typescript
// 单元测试示例
describe('AudioProcessor', () => {
  test('should convert audio file to float array', async () => {
    const mockUri = 'file://test.wav';
    const result = await AudioProcessor.audioFileToFloatArray(mockUri);
    expect(result).toBeInstanceOf(Float32Array);
  });
  
  test('should chunk audio data correctly', () => {
    const audioData = new Float32Array(1000);
    const chunks = AudioProcessor.chunkAudioData(audioData, 100);
    expect(chunks).toHaveLength(10);
  });
});
```

## 完整示例应用

```typescript
// App.tsx
import React from 'react';
import { SafeAreaView, StyleSheet } from 'react-native';
import { VoiceRecorder } from './components/VoiceRecorder';

export default function App() {
  const handleRecordingComplete = (audioData: Float32Array) => {
    console.log('录音完成，有效音频长度:', audioData.length);
    // 这里可以进行后续处理
  };
  
  return (
    <SafeAreaView style={styles.container}>
      <VoiceRecorder
        vadApiUrl="http://your-vad-api.com"
        backendApiUrl="http://your-backend-api.com"
        onRecordingComplete={handleRecordingComplete}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
});
```

## 总结

实现 Expo React Native 中的语音录制和 VAD 检测需要：

1. **正确配置音频录制参数**，确保格式兼容
2. **实现音频数据转换**，从文件到浮点数组
3. **集成 VAD API**，进行语音活动检测
4. **优化性能和用户体验**，包括压缩、缓存和错误处理

由于 Expo 的限制，完全的实时流式处理可能需要使用原生模块或等待 Expo 支持。建议先实现完整录制后检测的方案，再逐步优化到实时处理。