# ASR API Service 快速入门指南

这是一个基于现有 vad-based-streaming-asr 项目重构的现代化、生产就绪的 ASR API 服务。

## 🚀 10分钟快速启动

### 1. 环境准备

确保系统已安装：
- **Python 3.9+** (推荐 3.11+)
- **Git** 
- **curl** (用于测试)

### 2. 一键启动

```bash
# 进入项目目录
cd /Users/caixin/code/projects/meeting_code/asr_api_service

# 使用自动化脚本启动（推荐）
./scripts/start.sh dev
```

脚本会自动：
- ✅ 检查Python版本
- ✅ 创建虚拟环境
- ✅ 安装所有依赖
- ✅ 复制配置模板
- ✅ 创建数据目录
- ✅ 启动开发服务器

### 3. 配置API密钥

编辑生成的 `.env` 文件：

```bash
# 编辑配置文件
vim .env

# 必须设置的配置项：
ASR_PROVIDER=fireworks  # 或 openai
FIREWORKS_API_KEY=your_fireworks_api_key_here
# 或
# OPENAI_API_KEY=your_openai_api_key_here
```

### 4. 重新启动服务

```bash
# 停止当前服务 (Ctrl+C)
# 重新启动
./scripts/start.sh dev
```

## 🧪 验证部署

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

预期响应：
```json
{
  "status": "healthy",
  "service": "asr-api-service",
  "version": "0.1.0",
  "settings": {
    "asr_provider": "fireworks",
    "audio_sample_rate": 16000,
    "vad_threshold": 0.5
  }
}
```

### 2. 查看API文档

打开浏览器访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 3. 测试WebSocket流

```bash
# 使用提供的测试客户端
cd examples/
python streaming_client.py
```

## 🔧 手动安装（可选）

如果不使用自动化脚本：

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -e .

# 3. 配置环境
cp .env.example .env
# 编辑 .env 设置API密钥

# 4. 启动服务
asr-api serve --reload
```

## 📊 关键功能展示

### 1. 流式语音识别

```bash
# WebSocket端点
ws://localhost:8000/api/v1/stream
```

支持的消息类型：
- **config**: 配置API密钥和参数
- **audio**: 发送音频数据
- **control**: 控制命令（start/stop/reset）

### 2. 批量转录API

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@audio.wav" \
     -F "api_key=your_api_key"
```

### 3. 实时统计

```bash
curl http://localhost:8000/api/v1/streaming-stats
```

## 🛠️ 开发模式

### 启动开发服务器
```bash
./scripts/start.sh dev  # 带自动重载
```

### 运行测试
```bash
pip install -e ".[dev]"  # 安装测试依赖
pytest
```

### 代码格式化
```bash
black src/
isort src/
flake8 src/
```

## 🚀 生产部署

### Docker部署
```bash
# 构建镜像
docker build -t asr-api-service .

# 运行容器
docker run -d -p 8000:8000 --env-file .env asr-api-service
```

### Docker Compose
```bash
docker-compose up -d
```

### 系统服务
```bash
# 查看部署指南
cat DEPLOYMENT.md
```

## 🔄 从原项目迁移

如果您正在从原始的 vad-based-streaming-asr 迁移：

### 主要改进
- ✅ **现代化架构**: FastAPI + Pydantic + 异步处理
- ✅ **类型安全**: 完整的类型标注
- ✅ **模块化设计**: 清晰的代码结构和职责分离
- ✅ **配置管理**: 环境变量 + 验证
- ✅ **错误处理**: 结构化异常系统
- ✅ **生产就绪**: Docker、K8s、监控支持
- ✅ **文档齐全**: API文档 + 部署指南

### 兼容性
- ✅ **TEN-VAD集成**: 自动检测并使用现有 ../ten-vad/ 库
- ✅ **API兼容**: 支持相同的Whisper/Fireworks API
- ✅ **功能对等**: 保留所有核心VAD和ASR功能

### 配置映射

| 原配置 | 新配置 | 说明 |
|--------|--------|------|
| `whisper_api_key` | `FIREWORKS_API_KEY` | API密钥 |
| `vad_threshold` | `VAD_THRESHOLD` | VAD阈值 |
| `max_segment_duration` | `AUDIO_CHUNK_DURATION` | 音频分段 |
| `lookback_duration` | `AUDIO_LOOKBACK_DURATION` | 回看时长 |

## 🆘 常见问题

### Q: 服务启动后无法访问
**A:** 检查端口是否被占用，确认 `API_HOST=0.0.0.0`

### Q: API密钥配置错误
**A:** 确保 `.env` 文件中设置了正确的 `FIREWORKS_API_KEY` 或 `OPENAI_API_KEY`

### Q: TEN-VAD加载失败
**A:** 确保 `../ten-vad/` 目录存在，或服务会自动使用简单VAD fallback

### Q: WebSocket连接断开
**A:** 检查网络配置和防火墙设置，确认WebSocket支持

## 📚 更多资源

- **架构文档**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **部署指南**: [DEPLOYMENT.md](./DEPLOYMENT.md)
- **API文档**: http://localhost:8000/docs (服务启动后)
- **示例代码**: [examples/](./examples/)

## 🎯 下一步

1. **自定义配置**: 根据需求调整 `.env` 配置
2. **集成测试**: 使用您的音频数据测试
3. **性能调优**: 根据负载调整worker数量
4. **监控部署**: 启用Prometheus/Grafana监控
5. **生产部署**: 参考 DEPLOYMENT.md 进行生产环境部署

---

🎉 **恭喜！您已经成功部署了现代化的ASR API服务！**

如有问题，请查看详细文档或检查应用日志。