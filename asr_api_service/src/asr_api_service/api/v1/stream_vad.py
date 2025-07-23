"""流式VAD处理接口 - WebSocket版本"""

import asyncio
import json
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog
import numpy as np

from asr_api_service.core.audio.vad import VADProcessor
from asr_api_service.config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)

# 全局VAD处理器
_vad_processor: Optional[VADProcessor] = None

async def get_vad_processor() -> VADProcessor:
    """获取VAD处理器实例"""
    global _vad_processor
    if _vad_processor is None:
        _vad_processor = VADProcessor(
            threshold=settings.vad_threshold,
            silence_duration=settings.vad_silence_duration,
            hop_size=settings.vad_hop_size,
        )
    return _vad_processor


@router.websocket("/stream/vad")
async def stream_vad_processing(websocket: WebSocket):
    """
    流式VAD处理WebSocket接口
    
    消息格式:
    - 配置: {"type": "config", "sample_rate": 16000, "channels": 1}
    - 音频: {"type": "audio", "data": [float_array]}
    - 结束: {"type": "end"}
    
    返回格式:
    - VAD结果: {"type": "vad", "is_speaking": bool, "probability": float}
    - 状态: {"type": "status", "message": str}
    - 错误: {"type": "error", "message": str}
    """
    await websocket.accept()
    logger.info("WebSocket VAD连接建立")
    
    vad_processor = await get_vad_processor()
    sample_rate = 16000
    channels = 1
    buffer = []
    process_count = 0
    
    try:
        while True:
            # 接收消息
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data["type"] == "config":
                # 配置参数
                sample_rate = data.get("sample_rate", 16000)
                channels = data.get("channels", 1)
                
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "message": f"配置成功: {sample_rate}Hz, {channels}声道",
                    "use_real_vad": vad_processor.use_real_vad
                }))
                
            elif data["type"] == "audio":
                # 处理音频数据
                start_time = time.time()
                audio_chunk = data["data"]
                
                # 累积音频缓冲区
                buffer.extend(audio_chunk)
                
                # 当缓冲区足够大时处理
                window_size = 1024  # 可配置
                if len(buffer) >= window_size:
                    # 提取处理窗口
                    process_data = buffer[:window_size]
                    buffer = buffer[window_size//2:]  # 50%重叠
                    
                    # VAD处理
                    result = await vad_processor.process(process_data)
                    process_time = (time.time() - start_time) * 1000
                    process_count += 1
                    
                    # 发送结果
                    await websocket.send_text(json.dumps({
                        "type": "vad",
                        "is_speaking": result.is_speaking,
                        "probability": round(result.probability, 3),
                        "current_state": result.current_state,
                        "state_changed": result.state_changed,
                        "rms": round(result.rms, 4),
                        "processing_time_ms": round(process_time, 1),
                        "frame_count": process_count
                    }))
                    
            elif data["type"] == "end":
                # 处理剩余缓冲区
                if buffer:
                    result = await vad_processor.process(buffer)
                    await websocket.send_text(json.dumps({
                        "type": "vad",
                        "is_speaking": result.is_speaking,
                        "probability": round(result.probability, 3),
                        "final": True
                    }))
                
                # 发送完成状态
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "message": f"处理完成，共处理 {process_count} 帧",
                    "total_frames": process_count
                }))
                break
                
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"未知消息类型: {data['type']}"
                }))
                
    except WebSocketDisconnect:
        logger.info("WebSocket VAD连接断开")
    except json.JSONDecodeError as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"JSON解析错误: {str(e)}"
        }))
    except Exception as e:
        logger.exception("WebSocket VAD处理错误")
        await websocket.send_text(json.dumps({
            "type": "error", 
            "message": f"处理错误: {str(e)}"
        }))
    finally:
        # 重置VAD状态
        vad_processor.reset()
        logger.info("VAD处理器状态已重置")


@router.websocket("/stream/vad-binary")
async def stream_vad_binary(websocket: WebSocket):
    """
    二进制流式VAD处理 - 更高效的版本
    
    协议:
    1. 文本配置消息: {"sample_rate": 16000, "window_size": 1024}
    2. 二进制音频数据: float32数组的bytes
    3. 文本结果: {"is_speaking": bool, "probability": float}
    """
    await websocket.accept()
    logger.info("二进制WebSocket VAD连接建立")
    
    vad_processor = await get_vad_processor()
    sample_rate = 16000
    window_size = 1024
    configured = False
    
    try:
        while True:
            if not configured:
                # 等待配置消息
                config_message = await websocket.receive_text()
                config = json.loads(config_message)
                sample_rate = config.get("sample_rate", 16000)
                window_size = config.get("window_size", 1024)
                configured = True
                
                await websocket.send_text(json.dumps({
                    "type": "ready",
                    "sample_rate": sample_rate,
                    "window_size": window_size,
                    "use_real_vad": vad_processor.use_real_vad
                }))
                continue
            
            # 接收二进制音频数据
            audio_bytes = await websocket.receive_bytes()
            
            if len(audio_bytes) == 0:  # 结束信号
                break
                
            # 解析float32数据
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            
            # VAD处理
            start_time = time.time()
            result = await vad_processor.process(audio_array.tolist())
            process_time = (time.time() - start_time) * 1000
            
            # 发送结果（文本格式，便于解析）
            await websocket.send_text(json.dumps({
                "is_speaking": result.is_speaking,
                "probability": round(result.probability, 3),
                "rms": round(result.rms, 4),
                "processing_time_ms": round(process_time, 1),
                "samples": len(audio_array)
            }))
            
    except WebSocketDisconnect:
        logger.info("二进制WebSocket VAD连接断开")
    except Exception as e:
        logger.exception("二进制WebSocket VAD处理错误")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
    finally:
        vad_processor.reset()


@router.get("/stream/status")
async def stream_status():
    """获取流式处理状态"""
    vad_processor = await get_vad_processor()
    stats = vad_processor.get_stats()
    
    return {
        "status": "ready",
        "vad_type": "TEN-VAD" if stats["use_real_vad"] else "Simple VAD",
        "endpoints": {
            "websocket_json": "/api/v1/stream/vad",
            "websocket_binary": "/api/v1/stream/vad-binary"
        },
        "recommended_config": {
            "sample_rate": 16000,
            "window_size": 1024,
            "channels": 1,
            "format": "float32"
        },
        "performance": {
            "binary_mode": "最高性能，推荐实时场景",
            "json_mode": "兼容性好，调试方便"
        }
    }