# Expo React Native VAD 快速开始指南

## 最简实现（5分钟上手）

### 1. 安装依赖

```bash
expo install expo-audio expo-file-system
npm install axios buffer
```

### 2. 创建简单的录音组件

```tsx
// SimpleVoiceRecorder.tsx
import React, { useState } from 'react';
import { View, Button, Text, Alert } from 'react-native';
import { Audio } from 'expo-audio';
import * as FileSystem from 'expo-file-system';
import axios from 'axios';

const VAD_API_URL = 'http://localhost:8000'; // 替换为你的 VAD API 地址
const BACKEND_API_URL = 'http://your-backend.com'; // 替换为你的后端地址

export default function SimpleVoiceRecorder() {
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // 开始录音
  const startRecording = async () => {
    try {
      // 请求权限
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('需要麦克风权限');
        return;
      }

      // 设置音频模式
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // 开始录音
      const { recording } = await Audio.Recording.createAsync({
        android: {
          extension: '.m4a',
          outputFormat: Audio.AndroidOutputFormat.MPEG_4,
          audioEncoder: Audio.AndroidAudioEncoder.AAC,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
        },
        ios: {
          extension: '.m4a',
          outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
          audioQuality: Audio.IOSAudioQuality.HIGH,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
        },
        web: {
          mimeType: 'audio/webm',
          bitsPerSecond: 128000,
        },
      });

      setRecording(recording);
    } catch (error) {
      console.error('开始录音失败:', error);
      Alert.alert('错误', '无法开始录音');
    }
  };

  // 停止录音并处理
  const stopRecording = async () => {
    if (!recording) return;

    try {
      setIsProcessing(true);
      
      // 停止录音
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      
      if (!uri) {
        throw new Error('没有录音文件');
      }

      // 读取音频文件
      const audioBase64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      // 简单的 WAV 转换（这里需要根据实际格式处理）
      // 为了演示，我们假设后端可以处理 base64 音频
      
      // 发送到 VAD API 分析
      const vadResponse = await axios.post(`${VAD_API_URL}/api/v1/vad/analyze-audio`, {
        audio_base64: audioBase64,
        format: 'm4a',
        sample_rate: 16000,
      });

      const speechSegments = vadResponse.data.speech_segments;
      
      if (speechSegments.length === 0) {
        Alert.alert('提示', '没有检测到语音');
        return;
      }

      // 发送到后端
      const backendResponse = await axios.post(`${BACKEND_API_URL}/api/audio/process`, {
        audio_base64: audioBase64,
        format: 'm4a',
        sample_rate: 16000,
        speech_segments: speechSegments,
      });

      Alert.alert('成功', '音频已发送到服务器');
      console.log('服务器响应:', backendResponse.data);

    } catch (error) {
      console.error('处理录音失败:', error);
      Alert.alert('错误', '处理录音失败');
    } finally {
      setRecording(null);
      setIsProcessing(false);
    }
  };

  return (
    <View style={{ flex: 1, justifyContent: 'center', padding: 20 }}>
      <Button
        title={recording ? '停止录音' : '开始录音'}
        onPress={recording ? stopRecording : startRecording}
        disabled={isProcessing}
      />
      {isProcessing && <Text style={{ textAlign: 'center', marginTop: 20 }}>处理中...</Text>}
    </View>
  );
}
```

### 3. 使用 PCM 数据的改进版本

```tsx
// ImprovedVoiceRecorder.tsx
import React, { useState } from 'react';
import { View, TouchableOpacity, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Audio } from 'expo-audio';
import * as FileSystem from 'expo-file-system';
import axios from 'axios';

const VAD_API_URL = 'http://localhost:8000';

export default function ImprovedVoiceRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);

  // 将音频文件转换为 PCM 数据
  const convertAudioToPCM = async (uri: string): Promise<number[]> => {
    // 读取文件
    const fileInfo = await FileSystem.getInfoAsync(uri);
    console.log('文件信息:', fileInfo);

    // 这里需要实现音频格式转换
    // 由于 Expo 限制，可能需要：
    // 1. 使用服务器端转换
    // 2. 使用 WebAssembly 库
    // 3. 使用原生模块

    // 临时方案：发送原始文件到服务器转换
    const base64 = await FileSystem.readAsStringAsync(uri, {
      encoding: FileSystem.EncodingType.Base64,
    });

    const response = await axios.post(`${VAD_API_URL}/api/v1/convert-audio`, {
      audio_base64: base64,
      output_format: 'pcm_f32',
      sample_rate: 16000,
    });

    return response.data.audio_data;
  };

  const handlePressIn = async () => {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        alert('需要麦克风权限');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // 使用 WAV 格式以便更容易处理
      const recordingOptions = {
        android: {
          extension: '.wav',
          outputFormat: Audio.AndroidOutputFormat.PCM_16BIT,
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

      const { recording } = await Audio.Recording.createAsync(recordingOptions);
      setRecording(recording);
      setIsRecording(true);
    } catch (error) {
      console.error('开始录音失败:', error);
    }
  };

  const handlePressOut = async () => {
    if (!recording) return;

    try {
      setIsRecording(false);
      setIsProcessing(true);

      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      
      if (!uri) throw new Error('没有录音文件');

      // 转换音频格式
      const pcmData = await convertAudioToPCM(uri);
      
      // VAD 分析
      const vadResponse = await axios.post(`${VAD_API_URL}/api/v1/vad/analyze-file`, {
        audio_data: pcmData,
        sample_rate: 16000,
        window_duration: 0.5,
        overlap: 0.1,
      });

      const { speech_segments, statistics } = vadResponse.data;
      
      console.log('VAD 分析结果:', statistics);

      if (speech_segments.length === 0) {
        alert('没有检测到语音');
        return;
      }

      // 提取有效语音段
      const validAudioSegments = extractValidSegments(pcmData, speech_segments, 16000);
      
      // 发送到后端
      await sendToBackend(validAudioSegments);
      
      alert('录音处理完成！');

    } catch (error) {
      console.error('处理失败:', error);
      alert('处理录音失败');
    } finally {
      setRecording(null);
      setIsProcessing(false);
    }
  };

  // 提取有效音频段
  const extractValidSegments = (
    audioData: number[],
    segments: Array<{ start: number; end: number }>,
    sampleRate: number
  ): number[] => {
    const validAudio: number[] = [];
    
    segments.forEach(segment => {
      const startSample = Math.floor(segment.start * sampleRate);
      const endSample = Math.floor(segment.end * sampleRate);
      
      validAudio.push(...audioData.slice(startSample, endSample));
    });
    
    return validAudio;
  };

  // 发送到后端
  const sendToBackend = async (audioData: number[]) => {
    // 这里可以选择不同的发送方式
    
    // 方式1：直接发送 PCM 数据
    await axios.post(`${BACKEND_API_URL}/api/audio/upload-pcm`, {
      audio_data: audioData,
      sample_rate: 16000,
      format: 'float32',
    });

    // 方式2：转换为 WAV 后发送
    // const wavBlob = createWAVFromPCM(audioData, 16000);
    // const formData = new FormData();
    // formData.append('audio', wavBlob, 'recording.wav');
    // await axios.post(`${BACKEND_API_URL}/api/audio/upload`, formData);
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={[
          styles.button,
          isRecording && styles.buttonRecording,
          isProcessing && styles.buttonProcessing,
        ]}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        disabled={isProcessing}
      >
        {isProcessing ? (
          <ActivityIndicator color="white" />
        ) : (
          <Text style={styles.buttonText}>
            {isRecording ? '松开停止' : '按住说话'}
          </Text>
        )}
      </TouchableOpacity>
      
      <Text style={styles.hint}>
        {isProcessing ? '正在处理...' : '按住按钮开始录音'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  button: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  buttonRecording: {
    backgroundColor: '#FF3B30',
    transform: [{ scale: 1.1 }],
  },
  buttonProcessing: {
    backgroundColor: '#8E8E93',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  hint: {
    marginTop: 20,
    fontSize: 14,
    color: '#666',
  },
});
```

## 关键注意事项

### 1. 音频格式问题

Expo Audio 的限制：
- 不支持直接获取 PCM 数据
- 录制的音频需要转换格式

解决方案：
1. **服务器端转换**（推荐）
   ```typescript
   // 在 VAD API 服务器添加音频转换端点
   @router.post("/api/v1/convert-audio")
   async def convert_audio(audio_base64: str, output_format: str):
       # 使用 ffmpeg 或 librosa 转换音频
       return {"audio_data": pcm_data}
   ```

2. **使用第三方库**
   ```bash
   npm install react-native-audio-recorder-player
   # 这个库支持更多音频操作
   ```

### 2. 实时处理限制

Expo 目前不支持实时音频流，解决方案：
1. 使用定时录制（每隔几秒录制一次）
2. 使用 Expo 开发构建（custom development build）
3. 等待 Expo 支持或使用 React Native CLI

### 3. 性能优化建议

1. **限制录音时长**
   ```typescript
   const MAX_RECORDING_DURATION = 60000; // 60秒
   setTimeout(() => {
     if (recording) {
       stopRecording();
     }
   }, MAX_RECORDING_DURATION);
   ```

2. **压缩音频数据**
   ```typescript
   // 降低采样率
   const downsampledData = downsample(audioData, 16000, 8000);
   ```

3. **分块发送**
   ```typescript
   // 大文件分块上传
   const CHUNK_SIZE = 1024 * 1024; // 1MB
   for (let i = 0; i < audioData.length; i += CHUNK_SIZE) {
     const chunk = audioData.slice(i, i + CHUNK_SIZE);
     await uploadChunk(chunk, i / CHUNK_SIZE);
   }
   ```

## 测试建议

### 1. 本地测试

```bash
# 启动 VAD API 服务
cd asr-api-service
python -m asr_api_service

# 使用 ngrok 暴露本地服务（用于真机测试）
ngrok http 8000
```

### 2. 模拟 VAD API

```typescript
// mockVAD.ts
export const mockAnalyzeAudio = async (audioData: number[]) => {
  // 模拟 VAD 响应
  return {
    speech_segments: [
      { start: 0.5, end: 2.3, duration: 1.8 },
      { start: 3.0, end: 5.5, duration: 2.5 },
    ],
    statistics: {
      total_duration: 6.0,
      total_speech_duration: 4.3,
      speech_ratio: 0.72,
    },
  };
};
```

## 下一步

1. **实现音频格式转换服务**
2. **添加用户界面优化**（波形显示、录音计时器）
3. **实现离线 VAD**（使用 TensorFlow.js）
4. **添加音频压缩和加密**
5. **实现断点续传和重试机制**

## 相关资源

- [Expo Audio 文档](https://docs.expo.dev/versions/latest/sdk/audio/)
- [VAD API 文档](../ASR_API_使用指南.md)
- [音频处理最佳实践](./audio-processing-best-practices.md)
- [React Native 音频库对比](https://github.com/react-native-audio/react-native-audio)