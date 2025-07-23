# FFmpeg 安装指南

为了支持更多音频格式（如 m4a, mp3, aac），需要安装 FFmpeg。

## 安装 FFmpeg

### macOS
```bash
# 使用 Homebrew（推荐）
brew install ffmpeg

# 或使用 MacPorts
sudo port install ffmpeg
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

### CentOS/RHEL/Fedora
```bash
# CentOS/RHEL
sudo yum install epel-release
sudo yum install ffmpeg

# Fedora
sudo dnf install ffmpeg
```

### Windows
1. 下载 FFmpeg：https://ffmpeg.org/download.html
2. 解压到目录（如 `C:\ffmpeg`）
3. 将 `C:\ffmpeg\bin` 添加到系统环境变量 PATH

## 验证安装

```bash
ffmpeg -version
```

如果看到版本信息，说明安装成功。

## 支持的格式

### 安装 FFmpeg 前
- **原生支持**: WAV, FLAC, OGG
- **错误**: 其他格式会返回 `Format not recognised` 错误

### 安装 FFmpeg 后
- **全格式支持**: WAV, FLAC, OGG, MP3, M4A, AAC, WEBM 等

## 检查 API 支持状态

访问健康检查端点：
```bash
curl http://localhost:8000/api/v1/mobile/health
```

返回示例：
```json
{
  "status": "healthy",
  "features": {
    "ffmpeg_available": true,
    "supported_formats": ["wav", "flac", "ogg", "m4a", "mp3", "webm", "aac"]
  },
  "format_support": {
    "native": ["wav", "flac", "ogg"],
    "extended": ["m4a", "mp3", "webm", "aac"],
    "total": 7
  },
  "recommendations": {
    "install_ffmpeg": false,
    "preferred_formats": ["wav", "m4a", "mp3"]
  }
}
```

## 故障排除

### 问题 1: 命令未找到
```
ffmpeg: command not found
```
**解决**: 确保 FFmpeg 已安装并添加到 PATH

### 问题 2: 权限问题
```
Permission denied
```
**解决**: 检查 FFmpeg 可执行权限，或使用 sudo 安装

### 问题 3: 编解码器缺失
```
Unknown encoder 'libx264'
```
**解决**: 安装完整版本的 FFmpeg，包含所有编解码器

### 问题 4: 临时文件权限
```
No such file or directory
```
**解决**: 检查系统临时目录权限，确保应用可以创建临时文件

## 性能考虑

- **FFmpeg 转换**: 会增加一些处理时间（通常 < 200ms）
- **内存使用**: 需要创建临时文件
- **建议**: 生产环境推荐使用 WAV 或 FLAC 格式以获得最佳性能

## Docker 部署

如果使用 Docker，在 Dockerfile 中添加：

```dockerfile
# Ubuntu/Debian 基础镜像
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Alpine 基础镜像
RUN apk add --no-cache ffmpeg
```