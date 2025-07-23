# Swagger UI 测试指南

## 访问 Swagger UI

启动服务后，访问：
```
http://localhost:8000/docs
```

## 可测试的移动端 API 接口

### 1. `/api/v1/mobile/process-audio-file` - 完整音频处理

**功能**: 上传音频文件，进行 VAD 检测和格式转换

**测试步骤**:
1. 找到 "mobile" 标签下的 `POST /api/v1/mobile/process-audio-file`
2. 点击 "Try it out"
3. 配置参数：
   - `audio`: 点击 "Choose File" 选择音频文件 (支持 wav, m4a, mp3, ogg, webm, flac)
   - `sample_rate`: 16000 (默认)
   - `enable_vad`: true (启用语音检测)
   - `vad_window_duration`: 0.5 (VAD 窗口时长)
   - `vad_overlap`: 0.1 (VAD 窗口重叠)
   - `return_format`: 选择 "segments", "base64", 或 "merged"
   - `compress_output`: false (是否压缩输出)
4. 点击 "Execute"

**响应示例**:
```json
{
  "success": true,
  "message": "音频处理成功",
  "has_speech": true,
  "speech_segments": [
    {
      "start": 0.5,
      "end": 3.2,
      "duration": 2.7
    }
  ],
  "speech_ratio": 0.75,
  "total_duration": 3.6,
  "audio_data": [0.1, -0.2, 0.3, ...],  // 如果 return_format = "segments"
  "processing_time_ms": 245
}
```

### 2. `/api/v1/mobile/quick-vad-file` - 快速语音检测

**功能**: 快速检测音频是否包含语音，响应极快

**测试步骤**:
1. 找到 `POST /api/v1/mobile/quick-vad-file`
2. 点击 "Try it out"
3. 配置参数：
   - `audio`: 选择音频文件
   - `sample_rate`: 16000
4. 点击 "Execute"

**响应示例**:
```json
{
  "filename": "test.wav",
  "format": "wav",
  "file_size": 123456,
  "has_speech": true,
  "rms": 0.125,
  "duration": 3.5,
  "processing_time_ms": 45
}
```

### 3. `/api/v1/mobile/batch-process` - 批量处理

**功能**: 一次上传多个音频文件进行处理

**测试步骤**:
1. 找到 `POST /api/v1/mobile/batch-process`
2. 点击 "Try it out"
3. 配置参数：
   - `audio_files`: 选择多个音频文件（可以按住 Ctrl/Cmd 多选）
   - `enable_vad`: true
   - `merge_results`: true (是否合并所有有效音频)
4. 点击 "Execute"

## 测试建议

### 1. 准备测试音频

建议准备以下类型的音频文件：
- **纯语音**: 清晰的人声录音 (3-10秒)
- **静音**: 无声音或环境噪音
- **混合**: 包含语音和静音段
- **不同格式**: wav, mp3, m4a 等

### 2. 测试用例

#### 测试用例 1: 基本语音检测
- 上传一个包含清晰语音的 WAV 文件
- 预期: `has_speech: true`, `speech_ratio > 0.8`

#### 测试用例 2: 静音检测
- 上传一个静音文件或背景噪音
- 预期: `has_speech: false`, `speech_ratio < 0.1`

#### 测试用例 3: 格式兼容性
- 分别上传 wav, mp3, m4a 格式的同一音频
- 预期: 返回结果基本一致

#### 测试用例 4: 返回格式测试
- 使用相同音频，测试不同的 `return_format`:
  - `segments`: 返回 PCM 数组
  - `base64`: 返回 Base64 编码的音频
  - `merged`: 返回两者

### 3. 性能测试

#### 文件大小测试
```
小文件 (< 1MB):   应在 < 500ms 内处理完成
中等文件 (1-5MB): 应在 < 2s 内处理完成
大文件 (5-10MB):  应在 < 5s 内处理完成
```

#### 并发测试
- 可以在多个浏览器标签页同时发送请求
- 观察服务器的并发处理能力

## 常见问题与解决

### 问题 1: 文件上传失败
**错误**: `413 Request Entity Too Large`
**解决**: 文件过大，建议使用小于 10MB 的音频文件

### 问题 2: 格式不支持
**错误**: `无法转换音频格式`
**解决**: 确保上传的是支持的音频格式，或安装 ffmpeg

### 问题 3: VAD 检测结果异常
**可能原因**:
- 音频质量差
- 采样率设置错误
- VAD 参数需要调整

**调试方法**:
1. 先用 `quick-vad-file` 快速检测
2. 查看返回的 `rms` 值判断音频能量
3. 调整 `vad_window_duration` 和 `vad_overlap` 参数

### 问题 4: 处理时间过长
**优化建议**:
- 使用较短的音频文件 (< 30秒)
- 设置 `compress_output: false`
- 选择 `return_format: "segments"` 减少数据传输

## 高级测试技巧

### 1. 使用 curl 测试

```bash
# 快速 VAD 检测
curl -X POST "http://localhost:8000/api/v1/mobile/quick-vad-file" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@test.wav" \
  -F "sample_rate=16000"

# 完整音频处理
curl -X POST "http://localhost:8000/api/v1/mobile/process-audio-file" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@test.wav" \
  -F "sample_rate=16000" \
  -F "enable_vad=true" \
  -F "return_format=segments"
```

### 2. 使用 Python 脚本测试

```python
import requests

# 测试文件上传
with open('test.wav', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/mobile/process-audio-file',
        files={'audio': f},
        data={
            'sample_rate': 16000,
            'enable_vad': True,
            'return_format': 'segments'
        }
    )
    
print(response.json())
```

### 3. 自动化测试脚本

```python
import os
import requests
import time

def test_audio_files():
    """测试指定文件夹下的所有音频文件"""
    audio_folder = "test_audio"
    results = []
    
    for filename in os.listdir(audio_folder):
        if filename.endswith(('.wav', '.mp3', '.m4a')):
            filepath = os.path.join(audio_folder, filename)
            
            with open(filepath, 'rb') as f:
                start_time = time.time()
                
                response = requests.post(
                    'http://localhost:8000/api/v1/mobile/quick-vad-file',
                    files={'audio': f},
                    data={'sample_rate': 16000}
                )
                
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    results.append({
                        'filename': filename,
                        'has_speech': data['has_speech'],
                        'duration': data['duration'],
                        'processing_time': end_time - start_time,
                        'api_time': data['processing_time_ms']
                    })
    
    return results

# 运行测试
results = test_audio_files()
for result in results:
    print(f"{result['filename']}: {'✓' if result['has_speech'] else '✗'} "
          f"({result['duration']:.1f}s, {result['processing_time']:.3f}s)")
```

## API 健康检查

定期检查 API 状态：
```bash
curl http://localhost:8000/api/v1/mobile/health
```

这会返回所有可用的端点和配置信息，帮助确认服务正常运行。