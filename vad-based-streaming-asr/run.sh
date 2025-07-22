#!/bin/bash

echo "Starting VAD-Based Streaming ASR Server..."
echo ""
echo "Requirements:"
echo "- Python 3.7+"
echo "- pip install websockets numpy requests"
echo ""

# 检查Python版本
python3 --version

# 启动服务器
python3 server_main.py