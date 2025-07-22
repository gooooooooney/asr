# 智能会议助手

一个基于Web的实时会议转录和智能助手工具。

## 功能特性

1. **实时语音转录** - 使用Web Speech API进行流式ASR
2. **高性能VAD** - 使用TEN-VAD进行精确的语音活动检测
3. **智能意图识别** - 基于Gemini API的语义理解
4. **智能搜索** - RAG知识库 + Gemini搜索
5. **语音合成(TTS)** - 通过"小爱同学"唤醒词控制播报

## 快速开始

1. 启动本地服务器:
   ```bash
   python3 server.py
   ```

2. 在浏览器中访问 `http://localhost:8000`

3. 输入你的Gemini API密钥

4. 等待连接测试成功后开始使用

## 测试TEN-VAD

### 方法1：测试页面
访问 `http://localhost:8000/test-vad.html`，按步骤：
1. 点击"加载 TEN VAD"
2. 点击"初始化 VAD"
3. 点击"开始录音"测试

### 方法2：控制台测试
1. 打开浏览器控制台
2. 加载测试脚本：
   ```javascript
   const script = document.createElement('script');
   script.src = 'vad-test.js';
   document.head.appendChild(script);
   ```
3. 运行测试：
   ```javascript
   testTenVAD()
   ```

## 使用示例

### 意图识别（无需唤醒词）
- "哎，我忘记昨天我去哪里买的这个东西了"
- "昨天三元里发生危险了吗？"
- "有什么公司在出售AI玩具"

### TTS播报（需要唤醒词）
- 先进行搜索，然后说"小爱同学"播报结果

## 技术架构

- **语音识别**: Web Speech API (16kHz)
- **VAD**: TEN-VAD (256样本/16ms窗口)
- **意图识别**: Gemini API (每10字符检测)
- **搜索**: RAG + Gemini API
- **TTS**: Web Speech Synthesis API

## 配置说明

### Gemini API密钥
获取方式：https://makersuite.google.com/app/apikey

### VAD参数
- 采样率：16000Hz
- 窗口大小：256样本（16ms）
- 阈值：0.5
- 静音时长：800ms

## 故障排除

### VAD不工作
1. 检查控制台错误
2. 确认文件路径：
   - `public/ten_vad.js`
   - `public/ten_vad.wasm`
3. 使用测试页面验证

### 意图识别不准确
1. 检查Gemini API密钥
2. 确认网络连接
3. 查看控制台API响应

## 注意事项

- 需要Chrome/Edge浏览器
- 需要麦克风权限
- 需要稳定网络连接