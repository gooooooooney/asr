#!/usr/bin/env python3
"""
主服务器入口 - 同时启动HTTP服务器和WebSocket服务器
"""

import os
os.environ['https_proxy'] = 'http://127.0.0.1:7890'
os.environ['http_proxy'] = 'http://127.0.0.1:7890'

import sys
import asyncio
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import logging

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入WebSocket服务器
from server import main as websocket_main

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CORSRequestHandler(SimpleHTTPRequestHandler):
    """支持CORS的HTTP请求处理器"""
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def run_http_server(port=8080):
    """运行HTTP服务器"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    with HTTPServer(('', port), CORSRequestHandler) as httpd:
        logger.info(f"HTTP Server started at http://localhost:{port}")
        logger.info(f"Open http://localhost:{port}/index.html in your browser")
        httpd.serve_forever()

def run_websocket_server():
    """运行WebSocket服务器"""
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(websocket_main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

def main():
    """主函数"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║          VAD-Based Streaming ASR Server                  ║
    ╠══════════════════════════════════════════════════════════╣
    ║  HTTP Server:      http://localhost:8080                 ║
    ║  WebSocket Server: ws://localhost:8765                   ║
    ║                                                          ║
    ║  Open http://localhost:8080/index.html to start         ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # 启动WebSocket服务器线程
    ws_thread = threading.Thread(target=run_websocket_server, daemon=True)
    ws_thread.start()
    
    try:
        # 在主线程运行HTTP服务器
        run_http_server()
    except KeyboardInterrupt:
        logger.info("\nShutting down servers...")
        sys.exit(0)

if __name__ == "__main__":
    main()