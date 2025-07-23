#!/usr/bin/env python3
"""VAD API 使用示例 - 展示如何使用独立的VAD REST API"""

import requests
import numpy as np
import time
from typing import List


def generate_test_audio(duration: float = 1.0, sample_rate: int = 16000, 
                       has_speech: bool = True) -> List[float]:
    """生成测试音频数据
    
    参数:
        duration: 音频时长（秒）
        sample_rate: 采样率
        has_speech: 是否包含语音（True生成类语音信号，False生成静音）
    """
    samples = int(duration * sample_rate)
    
    if has_speech:
        # 生成类似语音的复杂信号
        t = np.linspace(0, duration, samples)
        # 多个频率叠加模拟语音
        signal = (0.3 * np.sin(2 * np.pi * 200 * t) +     # 基频
                  0.2 * np.sin(2 * np.pi * 400 * t) +     # 第一谐波
                  0.1 * np.sin(2 * np.pi * 800 * t) +     # 第二谐波
                  0.05 * np.random.normal(0, 1, samples))  # 噪声
        # 添加振幅调制模拟语音节奏
        envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)
        signal = signal * envelope
    else:
        # 生成低能量噪声（静音）
        signal = 0.01 * np.random.normal(0, 1, samples)
    
    # 限制到有效范围
    signal = np.clip(signal, -1.0, 1.0)
    return signal.tolist()


def example_single_detection():
    """示例1: 单次VAD检测"""
    print("\n=== 示例1: 单次VAD检测 ===")
    
    # API端点
    url = "http://localhost:8000/api/v1/vad/detect"
    
    # 测试语音检测
    print("\n1. 检测包含语音的音频:")
    speech_audio = generate_test_audio(duration=0.5, has_speech=True)
    
    response = requests.post(url, json={
        "audio_data": speech_audio,
        "sample_rate": 16000
    })
    
    if response.status_code == 200:
        result = response.json()
        print(f"   是否说话: {result['is_speaking']}")
        print(f"   状态: {result['state']}")
        print(f"   概率: {result['probability']}")
        print(f"   RMS能量: {result['rms']}")
        print(f"   处理时间: {result['processing_time_ms']}ms")
    else:
        print(f"   错误: {response.json()}")
    
    # 测试静音检测
    print("\n2. 检测静音音频:")
    silence_audio = generate_test_audio(duration=0.5, has_speech=False)
    
    response = requests.post(url, json={
        "audio_data": silence_audio,
        "sample_rate": 16000
    })
    
    if response.status_code == 200:
        result = response.json()
        print(f"   是否说话: {result['is_speaking']}")
        print(f"   状态: {result['state']}")
        print(f"   概率: {result['probability']}")
        print(f"   RMS能量: {result['rms']}")


def example_batch_processing():
    """示例2: 批量处理多个音频片段"""
    print("\n=== 示例2: 批量处理音频片段 ===")
    
    url = "http://localhost:8000/api/v1/vad/process-segments"
    
    # 生成测试片段：语音-静音-语音-静音模式
    segments = [
        generate_test_audio(0.3, has_speech=True),   # 语音
        generate_test_audio(0.3, has_speech=False),  # 静音
        generate_test_audio(0.3, has_speech=True),   # 语音
        generate_test_audio(0.3, has_speech=False),  # 静音
        generate_test_audio(0.3, has_speech=True),   # 语音
    ]
    
    response = requests.post(url, json={
        "segments": segments,
        "sample_rate": 16000,
        "reset_between_segments": False  # 保持VAD状态连续
    })
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"\n处理了 {result['summary']['total_segments']} 个片段:")
        print(f"- 语音片段: {result['summary']['speech_segments']}")
        print(f"- 静音片段: {result['summary']['silence_segments']}")
        print(f"- 语音比例: {result['summary']['speech_ratio']}")
        
        print("\n各片段结果:")
        for seg in result['segments']:
            state = "语音" if seg['is_speaking'] else "静音"
            print(f"  片段 {seg['segment_index']}: {state} (概率: {seg['probability']})")


def example_file_analysis():
    """示例3: 分析整个音频文件的语音活动分布"""
    print("\n=== 示例3: 音频文件VAD分析 ===")
    
    url = "http://localhost:8000/api/v1/vad/analyze-file"
    
    # 生成一个包含多个语音段的模拟音频文件
    audio_parts = []
    
    # 创建模式: 静音(1s) - 语音(2s) - 静音(0.5s) - 语音(1.5s) - 静音(1s)
    audio_parts.extend(generate_test_audio(1.0, has_speech=False))   # 静音
    audio_parts.extend(generate_test_audio(2.0, has_speech=True))    # 语音
    audio_parts.extend(generate_test_audio(0.5, has_speech=False))   # 静音
    audio_parts.extend(generate_test_audio(1.5, has_speech=True))    # 语音
    audio_parts.extend(generate_test_audio(1.0, has_speech=False))   # 静音
    
    response = requests.post(url, json={
        "audio_data": audio_parts,
        "sample_rate": 16000,
        "window_duration": 0.5,  # 500ms窗口
        "overlap": 0.1          # 100ms重叠
    })
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"\n音频文件分析结果:")
        print(f"- 总时长: {result['statistics']['total_duration']}秒")
        print(f"- 语音时长: {result['statistics']['total_speech_duration']}秒")
        print(f"- 静音时长: {result['statistics']['total_silence_duration']}秒")
        print(f"- 语音比例: {result['statistics']['speech_ratio']}")
        
        print(f"\n检测到 {len(result['speech_segments'])} 个语音段:")
        for i, seg in enumerate(result['speech_segments']):
            print(f"  语音段 {i+1}: {seg['start']}s - {seg['end']}s (时长: {seg['duration']}s)")


def example_real_time_simulation():
    """示例4: 模拟实时VAD处理"""
    print("\n=== 示例4: 模拟实时VAD处理 ===")
    
    url = "http://localhost:8000/api/v1/vad/detect"
    
    # 模拟实时音频流
    chunk_duration = 0.1  # 100ms块
    sample_rate = 16000
    
    # 语音模式序列
    speech_pattern = [False, False, True, True, True, False, True, True, False, False]
    
    print("\n开始模拟实时处理...")
    print("时间 | 状态  | 概率   | 状态变化")
    print("-" * 40)
    
    for i, has_speech in enumerate(speech_pattern):
        # 生成音频块
        audio_chunk = generate_test_audio(chunk_duration, sample_rate, has_speech)
        
        # 发送VAD请求
        response = requests.post(url, json={
            "audio_data": audio_chunk,
            "sample_rate": sample_rate
        })
        
        if response.status_code == 200:
            result = response.json()
            
            time_str = f"{i * chunk_duration:.1f}s"
            state = "语音" if result['is_speaking'] else "静音"
            prob = f"{result['probability']:.3f}"
            changed = "是" if result['state_changed'] else "否"
            
            print(f"{time_str:4} | {state:4} | {prob:6} | {changed}")
        
        # 模拟实时延迟
        time.sleep(0.05)


def example_vad_status():
    """示例5: 获取VAD状态信息"""
    print("\n=== 示例5: 获取VAD状态 ===")
    
    # 获取当前状态
    response = requests.get("http://localhost:8000/api/v1/vad/status")
    
    if response.status_code == 200:
        status = response.json()
        
        print("\nVAD处理器状态:")
        print(f"- 状态: {status['status']}")
        print(f"- VAD类型: {status['current_state']['vad_type']}")
        print(f"- TEN-VAD可用: {status['capabilities']['ten_vad_available']}")
        
        print("\n配置信息:")
        print(f"- 阈值: {status['configuration']['threshold']}")
        print(f"- 静音时长: {status['configuration']['silence_duration']}秒")
        print(f"- 跳跃大小: {status['configuration']['hop_size']}样本")
        
        print("\n支持的采样率:")
        for rate in status['capabilities']['supported_sample_rates']:
            print(f"  - {rate} Hz")
    
    # 重置VAD状态
    print("\n重置VAD状态...")
    response = requests.post("http://localhost:8000/api/v1/vad/reset")
    if response.status_code == 200:
        print("VAD状态已重置")


def main():
    """运行所有示例"""
    print("VAD API 使用示例")
    print("=" * 50)
    print("注意: 请确保ASR API服务正在运行 (http://localhost:8000)")
    
    try:
        # 检查服务是否可用
        response = requests.get("http://localhost:8000/health")
        if response.status_code != 200:
            print("错误: ASR API服务不可用")
            return
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到ASR API服务")
        print("请先启动服务: python -m asr_api_service")
        return
    
    # 运行示例
    example_single_detection()
    example_batch_processing()
    example_file_analysis()
    example_real_time_simulation()
    example_vad_status()
    
    print("\n所有示例运行完成！")


if __name__ == "__main__":
    main()