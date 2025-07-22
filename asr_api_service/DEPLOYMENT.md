# ASR API Service 部署指南

本文档提供了ASR API Service的多种部署方案，包括开发环境、生产环境、Docker容器化部署以及Kubernetes集群部署。

## 目录

- [快速开始](#快速开始)
- [开发环境部署](#开发环境部署)
- [生产环境部署](#生产环境部署)
- [Docker部署](#docker部署)
- [Kubernetes部署](#kubernetes部署)
- [监控与日志](#监控与日志)
- [性能优化](#性能优化)
- [故障排除](#故障排除)

## 快速开始

### 系统要求

- **操作系统**: Ubuntu 20.04+, CentOS 8+, macOS 10.15+, Windows 10+
- **Python**: 3.9+ (推荐 3.11+)
- **内存**: 最低 2GB，推荐 4GB+
- **CPU**: 2核心+
- **存储**: 10GB+ 可用空间
- **网络**: 需要访问外部API服务 (OpenAI/Fireworks)

### 依赖服务

- **TEN-VAD**: 语音活动检测库 (可选，有fallback)
- **外部API**: Whisper/OpenAI/Fireworks API
- **数据库**: 无需数据库 (未来可能支持PostgreSQL)
- **缓存**: 无需Redis (未来可能支持)

## 开发环境部署

### 1. 克隆项目

```bash
cd /Users/caixin/code/projects/meeting_code/
# 项目已经在 asr_api_service/ 目录下
cd asr_api_service
```

### 2. 创建虚拟环境

```bash
# 使用 Python 3.11 (推荐)
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\\Scripts\\activate  # Windows

# 升级pip
pip install --upgrade pip
```

### 3. 安装依赖

```bash
# 安装项目依赖
pip install -e .

# 安装开发依赖 (可选)
pip install -e ".[dev]"
```

### 4. 配置环境

```bash
# 复制环境配置文件
cp .env.example .env

# 编辑配置 (必须设置API密钥)
vim .env
```

**必须配置的环境变量:**
```bash
# 选择一个ASR提供商并设置相应的API密钥
ASR_PROVIDER=fireworks
FIREWORKS_API_KEY=your_fireworks_api_key_here

# 或者使用OpenAI
# ASR_PROVIDER=openai
# OPENAI_API_KEY=your_openai_api_key_here
```

### 5. 初始化项目

```bash
# 使用CLI工具初始化
asr-api init
```

### 6. 启动开发服务器

```bash
# 方式1: 使用CLI工具 (推荐)
asr-api serve --reload

# 方式2: 直接使用uvicorn
uvicorn asr_api_service.main:app --reload --host 0.0.0.0 --port 8000

# 方式3: 使用Python模块
python -m asr_api_service.main
```

### 7. 验证部署

```bash
# 检查健康状态
curl http://localhost:8000/health

# 查看API文档
open http://localhost:8000/docs

# 测试WebSocket连接
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: $(echo -n hello | base64)" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8000/api/v1/stream
```

## 生产环境部署

### 1. 系统准备

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev \
    build-essential curl nginx supervisor

# CentOS/RHEL
sudo dnf install -y python3.11 python3.11-devel gcc gcc-c++ make \
    curl nginx supervisor
```

### 2. 创建专用用户

```bash
# 创建系统用户
sudo useradd -r -s /bin/bash -d /opt/asr-api asr-api
sudo mkdir -p /opt/asr-api
sudo chown asr-api:asr-api /opt/asr-api
```

### 3. 部署应用

```bash
# 切换到应用用户
sudo -u asr-api -i

# 克隆或上传代码
cd /opt/asr-api
# ... 上传代码到此目录

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env.prod
# 编辑 .env.prod 设置生产环境配置
```

**生产环境配置示例 (.env.prod):**
```bash
# 生产环境设置
API_DEBUG=false
API_RELOAD=false
API_WORKERS=4
LOG_LEVEL=INFO
LOG_FORMAT=json
ENABLE_DOCS=false

# API配置
API_HOST=127.0.0.1  # 内部访问，通过Nginx代理
API_PORT=8000

# ASR配置
ASR_PROVIDER=fireworks
FIREWORKS_API_KEY=your_production_api_key

# 安全配置
SECRET_KEY=your-very-secret-production-key

# 存储配置
AUDIO_STORAGE_PATH=/opt/asr-api/data/audio
LOG_STORAGE_PATH=/opt/asr-api/data/logs
TEMP_STORAGE_PATH=/opt/asr-api/data/temp
```

### 4. 配置Systemd服务

```bash
sudo tee /etc/systemd/system/asr-api.service > /dev/null <<EOF
[Unit]
Description=ASR API Service
After=network.target

[Service]
Type=exec
User=asr-api
Group=asr-api
WorkingDirectory=/opt/asr-api
Environment=PATH=/opt/asr-api/venv/bin
EnvironmentFile=/opt/asr-api/.env.prod
ExecStart=/opt/asr-api/venv/bin/asr-api serve
Restart=always
RestartSec=10

# 安全设置
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/asr-api/data

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable asr-api
sudo systemctl start asr-api
```

### 5. 配置Nginx反向代理

```bash
sudo tee /etc/nginx/sites-available/asr-api > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;

    # 重定向到HTTPS (生产环境推荐)
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL配置
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;

    # WebSocket支持
    location /api/v1/stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }

    # API请求
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 文件上传大小限制
        client_max_body_size 100M;
    }

    # 静态文件缓存 (如果有)
    location /static/ {
        alias /opt/asr-api/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# 启用站点
sudo ln -s /etc/nginx/sites-available/asr-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Docker部署

### 1. 构建Docker镜像

```bash
# 在项目根目录
docker build -t asr-api-service:latest .

# 构建指定平台镜像 (如需要)
docker build --platform linux/amd64 -t asr-api-service:latest .
```

### 2. 运行单容器

```bash
# 创建环境文件
cp .env.example .env
# 编辑 .env 设置API密钥等配置

# 运行容器
docker run -d \
  --name asr-api \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  asr-api-service:latest
```

### 3. 使用Docker Compose (推荐)

```bash
# 基础服务
docker-compose up -d

# 包含Nginx反向代理
docker-compose --profile with-nginx up -d

# 包含监控服务 (Prometheus + Grafana)
docker-compose --profile monitoring up -d

# 完整服务栈
docker-compose --profile with-nginx --profile monitoring up -d
```

### 4. Docker部署验证

```bash
# 检查容器状态
docker ps
docker logs asr-api

# 健康检查
curl http://localhost:8000/health

# 查看容器资源使用
docker stats asr-api
```

## Kubernetes部署

### 1. 准备Kubernetes清单

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: asr-api

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: asr-api-config
  namespace: asr-api
data:
  API_HOST: "0.0.0.0"
  API_PORT: "8000"
  API_WORKERS: "4"
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: asr-api-secrets
  namespace: asr-api
type: Opaque
stringData:
  FIREWORKS_API_KEY: "your-api-key-here"
  SECRET_KEY: "your-secret-key-here"

---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: asr-api
  namespace: asr-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: asr-api
  template:
    metadata:
      labels:
        app: asr-api
    spec:
      containers:
      - name: asr-api
        image: asr-api-service:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: asr-api-config
        - secretRef:
            name: asr-api-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: asr-api-pvc

---
# k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: asr-api-pvc
  namespace: asr-api
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: asr-api-service
  namespace: asr-api
spec:
  selector:
    app: asr-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: asr-api-ingress
  namespace: asr-api
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - asr-api.yourdomain.com
    secretName: asr-api-tls
  rules:
  - host: asr-api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: asr-api-service
            port:
              number: 80
```

### 2. 部署到Kubernetes

```bash
# 应用所有清单
kubectl apply -f k8s/

# 检查部署状态
kubectl get all -n asr-api

# 查看Pod日志
kubectl logs -f deployment/asr-api -n asr-api

# 端口转发测试 (可选)
kubectl port-forward svc/asr-api-service 8000:80 -n asr-api
```

## 监控与日志

### 1. 应用监控

```bash
# 健康检查端点
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/streaming-health

# 应用统计信息
curl http://localhost:8000/api/v1/streaming-stats
```

### 2. 系统监控

使用Docker Compose的监控栈:

```bash
# 启动监控服务
docker-compose --profile monitoring up -d

# 访问Grafana: http://localhost:3000 (admin/admin)
# 访问Prometheus: http://localhost:9090
```

### 3. 日志管理

```bash
# 查看应用日志
journalctl -u asr-api -f  # Systemd
docker logs -f asr-api    # Docker

# 日志文件位置
tail -f /opt/asr-api/data/logs/asr-api-service.log

# 日志轮转配置 (在生产环境中)
sudo tee /etc/logrotate.d/asr-api > /dev/null <<EOF
/opt/asr-api/data/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
```

## 性能优化

### 1. 系统级优化

```bash
# 调整系统限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 网络优化
echo 'net.core.somaxconn = 65536' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_max_syn_backlog = 65536' >> /etc/sysctl.conf
sysctl -p
```

### 2. 应用级优化

**环境配置优化:**
```bash
# .env.prod
API_WORKERS=4  # CPU核心数
STREAMING_MAX_CLIENTS=200
AUDIO_CHUNK_DURATION=2.0  # 减少延迟
VAD_THRESHOLD=0.35  # 调整VAD敏感度
```

**内存优化:**
```bash
# 限制音频缓存
AUDIO_MAX_DURATION=120.0
AUDIO_LOOKBACK_DURATION=6.0
```

### 3. 负载均衡

使用Nginx配置多实例负载均衡:

```nginx
upstream asr_api_backend {
    least_conn;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    location / {
        proxy_pass http://asr_api_backend;
        # ... 其他配置
    }
}
```

## 故障排除

### 1. 常见问题

**API连接失败:**
```bash
# 检查API密钥配置
asr-api config check

# 测试网络连接
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.openai.com/v1/models
```

**TEN-VAD加载失败:**
```bash
# 检查TEN-VAD路径
ls -la ../ten-vad/include/

# 查看VAD状态
curl http://localhost:8000/api/v1/streaming-health
```

**WebSocket连接问题:**
```bash
# 检查Nginx配置
nginx -t

# 查看连接状态
netstat -tulpn | grep 8000
```

### 2. 日志分析

**关键错误模式:**
```bash
# ASR API错误
grep "ASR.*error" /opt/asr-api/data/logs/*.log

# VAD处理错误
grep "VAD.*error" /opt/asr-api/data/logs/*.log

# WebSocket连接错误
grep "websocket.*error" /opt/asr-api/data/logs/*.log
```

### 3. 性能分析

```bash
# 资源使用监控
htop
iotop

# 网络连接监控
ss -tulpn | grep 8000

# 应用性能指标
curl http://localhost:8000/api/v1/streaming-stats | jq .
```

### 4. 紧急恢复

```bash
# 重启服务
sudo systemctl restart asr-api

# 清理缓存和临时文件
rm -rf /opt/asr-api/data/temp/*

# 检查磁盘空间
df -h /opt/asr-api/data/

# 数据库重置 (如果使用)
# dropdb asr_api && createdb asr_api
```

## 维护和更新

### 1. 应用更新

```bash
# 备份配置
cp .env.prod .env.prod.backup

# 更新代码
git pull origin main

# 更新依赖
pip install -e .

# 重启服务
sudo systemctl restart asr-api
```

### 2. 数据备份 (如需要)

```bash
# 备份音频文件
tar -czf backup_$(date +%Y%m%d).tar.gz /opt/asr-api/data/audio/

# 备份日志
tar -czf logs_$(date +%Y%m%d).tar.gz /opt/asr-api/data/logs/
```

### 3. 监控指标

定期检查以下指标:
- API响应时间
- WebSocket连接数
- 音频处理成功率
- 系统资源使用率
- 错误率和错误类型

---

## 技术支持

如遇到问题，请按以下顺序排查:

1. 查看应用日志
2. 检查系统资源
3. 验证网络连接
4. 测试API密钥
5. 查看本文档的故障排除部分

更多技术文档请参考 [ARCHITECTURE.md](./ARCHITECTURE.md) 和 [README.md](./README.md)。