#!/usr/bin/env python3
"""
音频传输方案性能对比客户端
演示不同传输方式的性能差异
"""

import asyncio
import websockets
import json
import time
import base64
import numpy as np
import requests
from pathlib import Path
import io
import soundfile as sf

class AudioTransmissionTester:
    def __init__(self, base_url="http://localhost:8000", ws_url="ws://localhost:8000"):
        self.base_url = base_url
        self.ws_url = ws_url
    
    def generate_test_audio(self, duration=10, sample_rate=16000):
        """生成测试音频数据"""
        t = np.linspace(0, duration, sample_rate * duration, False)
        # 生成包含语音特征的音频
        frequency = 440  # A4音符
        audio = np.sin(2 * np.pi * frequency * t) * 0.3
        # 添加一些噪音模拟真实语音
        noise = np.random.normal(0, 0.05, audio.shape)
        audio = audio + noise
        return audio.astype(np.float32), sample_rate
    
    def save_audio_as_wav(self, audio, sample_rate, filename):
        """保存音频为WAV文件"""
        sf.write(filename, audio, sample_rate)
        return filename
    
    async def test_base64_method(self, audio, sample_rate):
        """测试Base64编码方法（原始方法）"""
        print("\n🔄 测试方案1: Base64编码传输")
        
        # 保存为WAV
        temp_file = "temp_test.wav"
        self.save_audio_as_wav(audio, sample_rate, temp_file)
        
        # 读取并编码为Base64
        start_time = time.time()
        with open(temp_file, 'rb') as f:
            audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        encode_time = time.time() - start_time
        
        # 发送请求
        start_time = time.time()
        response = requests.post(
            f"{self.base_url}/api/v1/mobile/process-audio",
            json={
                "audio_base64": audio_base64,
                "format": "wav",
                "sample_rate": sample_rate,
                "enable_vad": True,
                "return_format": "segments"
            }
        )
        request_time = time.time() - start_time
        
        result = response.json() if response.status_code == 200 else None
        
        print(f"  📊 数据大小: {len(audio_base64):,} 字符")
        print(f"  ⏱️ 编码耗时: {encode_time*1000:.1f}ms")
        print(f"  🌐 请求耗时: {request_time*1000:.1f}ms")
        print(f"  📈 总耗时: {(encode_time + request_time)*1000:.1f}ms")
        if result:
            print(f"  ✅ 处理成功: {result.get('message', 'OK')}")
        else:
            print(f"  ❌ 请求失败: {response.status_code}")
        
        # 清理临时文件
        Path(temp_file).unlink(missing_ok=True)
        return encode_time + request_time
    
    async def test_direct_upload_method(self, audio, sample_rate):
        """测试直接文件上传方法（优化方法）"""
        print("\n⚡ 测试方案2: 直接文件上传")
        
        # 保存为WAV
        temp_file = "temp_test.wav"
        self.save_audio_as_wav(audio, sample_rate, temp_file)
        
        # 直接上传文件
        start_time = time.time()
        with open(temp_file, 'rb') as f:
            files = {'audio': ('test.wav', f, 'audio/wav')}
            data = {
                'sample_rate': sample_rate,
                'enable_vad': True,
                'return_audio': False,
                'output_format': 'json'
            }
            response = requests.post(
                f"{self.base_url}/api/v1/mobile/process-audio-efficient",
                files=files,
                data=data
            )
        request_time = time.time() - start_time
        
        result = response.json() if response.status_code == 200 else None
        
        print(f"  📊 文件大小: {Path(temp_file).stat().st_size:,} 字节")
        print(f"  🌐 请求耗时: {request_time*1000:.1f}ms")
        print(f"  📈 总耗时: {request_time*1000:.1f}ms")
        if result:
            print(f"  ✅ 处理成功: {result.get('message', 'OK')}")
            print(f"  📝 优化说明: {result.get('efficiency_note', '')}")
        else:
            print(f"  ❌ 请求失败: {response.status_code}")
        
        # 清理临时文件
        Path(temp_file).unlink(missing_ok=True)
        return request_time
    
    async def test_websocket_binary_method(self, audio, sample_rate):
        """测试WebSocket二进制传输方法（最高效）"""
        print("\n🚀 测试方案3: WebSocket二进制流传输")
        
        try:
            start_time = time.time()
            
            # 连接WebSocket
            async with websockets.connect(f"{self.ws_url}/api/v1/stream/vad-binary") as websocket:
                # 发送配置
                config = {
                    "sample_rate": sample_rate,
                    "window_size": 1024
                }
                await websocket.send(json.dumps(config))
                
                # 等待确认
                response = await websocket.recv()
                config_result = json.loads(response)
                print(f"  📡 连接状态: {config_result.get('type', 'ready')}")
                
                # 分块发送音频数据
                window_size = 1024
                total_chunks = len(audio) // window_size
                processing_times = []
                
                for i in range(0, len(audio), window_size):
                    chunk = audio[i:i+window_size]
                    if len(chunk) < window_size:
                        # 补零到完整窗口大小
                        chunk = np.pad(chunk, (0, window_size - len(chunk)))
                    
                    # 发送二进制数据
                    chunk_start = time.time()
                    await websocket.send(chunk.astype(np.float32).tobytes())
                    
                    # 接收结果
                    response = await websocket.recv()
                    result = json.loads(response)
                    processing_times.append(result.get('processing_time_ms', 0))
                    chunk_time = time.time() - chunk_start
                
                # 发送结束信号
                await websocket.send(b'')
                
                total_time = time.time() - start_time
                
                print(f"  📊 传输块数: {total_chunks}")
                print(f"  📦 每块大小: {window_size * 4} 字节 (float32)")
                print(f"  ⏱️ 平均处理时间: {np.mean(processing_times):.1f}ms/块")
                print(f"  🌐 总传输时间: {total_time*1000:.1f}ms")
                print(f"  📈 实时因子: {(len(audio)/sample_rate)/(total_time):.2f}x")
                
                return total_time
                
        except Exception as e:
            print(f"  ❌ WebSocket连接失败: {e}")
            return float('inf')
    
    async def test_websocket_json_method(self, audio, sample_rate):
        """测试WebSocket JSON传输方法"""
        print("\n📡 测试方案4: WebSocket JSON流传输")
        
        try:
            start_time = time.time()
            
            async with websockets.connect(f"{self.ws_url}/api/v1/stream/vad") as websocket:
                # 发送配置
                config_msg = {
                    "type": "config",
                    "sample_rate": sample_rate,
                    "channels": 1
                }
                await websocket.send(json.dumps(config_msg))
                
                # 等待确认
                response = await websocket.recv()
                config_result = json.loads(response)
                print(f"  📡 连接状态: {config_result.get('message', 'ready')}")
                
                # 分块发送音频数据
                window_size = 1024
                total_chunks = len(audio) // window_size
                
                for i in range(0, len(audio), window_size):
                    chunk = audio[i:i+window_size]
                    
                    # 发送JSON格式数据
                    audio_msg = {
                        "type": "audio",
                        "data": chunk.tolist()
                    }
                    await websocket.send(json.dumps(audio_msg))
                    
                    # 接收结果
                    response = await websocket.recv()
                    result = json.loads(response)
                
                # 发送结束信号
                end_msg = {"type": "end"}
                await websocket.send(json.dumps(end_msg))
                
                # 接收最终状态
                response = await websocket.recv()
                final_result = json.loads(response)
                
                total_time = time.time() - start_time
                
                print(f"  📊 传输块数: {total_chunks}")
                print(f"  🌐 总传输时间: {total_time*1000:.1f}ms")
                print(f"  📈 实时因子: {(len(audio)/sample_rate)/(total_time):.2f}x")
                print(f"  ✅ 最终状态: {final_result.get('message', 'completed')}")
                
                return total_time
                
        except Exception as e:
            print(f"  ❌ WebSocket连接失败: {e}")
            return float('inf')
    
    async def run_comparison(self, duration=10):
        """运行完整的性能对比测试"""
        print("🎯 音频传输方案性能对比测试")
        print("=" * 50)
        
        # 生成测试音频
        audio, sample_rate = self.generate_test_audio(duration)
        print(f"📍 测试音频: {duration}秒, {sample_rate}Hz, {len(audio):,}样本")
        
        # 测试各种方案
        results = {}
        
        results['base64'] = await self.test_base64_method(audio, sample_rate)
        results['direct_upload'] = await self.test_direct_upload_method(audio, sample_rate)
        results['websocket_binary'] = await self.test_websocket_binary_method(audio, sample_rate)
        results['websocket_json'] = await self.test_websocket_json_method(audio, sample_rate)
        
        # 性能对比汇总
        print("\n" + "=" * 50)
        print("📊 性能对比汇总")
        print("=" * 50)
        
        baseline = results['base64']
        for method, time_cost in results.items():
            if time_cost == float('inf'):
                print(f"{method:20s}: ❌ 测试失败")
            else:
                speedup = baseline / time_cost if time_cost > 0 else 0
                print(f"{method:20s}: {time_cost*1000:7.1f}ms ({speedup:.2f}x)")
        
        # 推荐方案
        print("\n🎯 方案推荐:")
        
        if results['websocket_binary'] < float('inf'):
            print("🚀 实时场景: WebSocket二进制传输 (最高性能)")
        
        if results['direct_upload'] < float('inf'):
            print("📱 移动应用: 直接文件上传 (平衡性能与兼容性)")
        
        print("📋 批量处理: Base64编码 (兼容性最好)")


async def main():
    """主函数"""
    tester = AudioTransmissionTester()
    
    # 运行10秒音频的对比测试
    await tester.run_comparison(duration=10)


if __name__ == "__main__":
    asyncio.run(main())