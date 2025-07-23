"""VAD (Voice Activity Detection) API endpoints."""

import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
import structlog
import numpy as np

from asr_api_service.config import settings
from asr_api_service.core.audio.vad import VADProcessor, VADResult
from asr_api_service.exceptions import VADError, ValidationError
from asr_api_service.utils.validation import validate_audio_data

router = APIRouter()
logger = structlog.get_logger(__name__)


# 全局VAD处理器实例（可以根据需要改为依赖注入）
_vad_processor = None


async def get_vad_processor() -> VADProcessor:
    """获取或创建VAD处理器实例"""
    global _vad_processor
    if _vad_processor is None:
        _vad_processor = VADProcessor(
            threshold=settings.vad_threshold,
            silence_duration=settings.vad_silence_duration,
            hop_size=settings.vad_hop_size,
        )
    return _vad_processor


@router.post("/vad/detect")
async def detect_voice_activity(
    audio_data: List[float],
    sample_rate: int = 16000,
    vad_processor: VADProcessor = Depends(get_vad_processor),
):
    """检测音频中的语音活动
    
    参数:
        audio_data: 音频样本数据（-1.0到1.0的浮点数列表）
        sample_rate: 采样率（默认16000Hz）
    
    返回:
        VAD检测结果，包含语音状态、概率、能量等信息
    """
    start_time = time.time()
    
    try:
        # 验证音频数据
        if not audio_data:
            raise ValidationError("音频数据不能为空")
        
        if len(audio_data) < vad_processor.hop_size:
            raise ValidationError(
                f"音频数据太短，至少需要 {vad_processor.hop_size} 个样本"
            )
        
        # 验证采样率
        if sample_rate not in [8000, 16000, 22050, 44100, 48000]:
            logger.warning(
                "非标准采样率", 
                sample_rate=sample_rate,
                recommended=[16000, 44100, 48000]
            )
        
        logger.info(
            "VAD检测请求",
            audio_length=len(audio_data),
            sample_rate=sample_rate,
            duration_seconds=len(audio_data) / sample_rate,
        )
        
        # 执行VAD检测
        result = await vad_processor.process(audio_data)
        
        # 构建响应
        response = {
            "is_speaking": result.is_speaking,
            "state": result.current_state,  # 'speech' 或 'silence'
            "state_changed": result.state_changed,
            "probability": round(result.probability, 4),
            "rms": round(result.rms, 4),
            "max_amplitude": round(result.max_amplitude, 4),
            "silence_timeout": result.silence_timeout,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "metadata": {
                "sample_rate": sample_rate,
                "audio_length": len(audio_data),
                "duration_seconds": round(len(audio_data) / sample_rate, 2),
                "threshold": vad_processor.threshold,
                "silence_duration": vad_processor.silence_duration,
            }
        }
        
        logger.info(
            "VAD检测完成",
            is_speaking=result.is_speaking,
            state=result.current_state,
            probability=result.probability,
            processing_time_ms=response["processing_time_ms"],
        )
        
        return response
        
    except ValidationError as e:
        logger.warning("验证错误", error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    
    except VADError as e:
        logger.error("VAD处理错误", error=e.message, vad_info=e.vad_info)
        raise HTTPException(status_code=500, detail=e.message)
    
    except Exception as e:
        logger.exception("VAD检测时发生意外错误")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("/vad/process-segments")
async def process_audio_segments(
    segments: List[List[float]],
    sample_rate: int = 16000,
    reset_between_segments: bool = False,
    vad_processor: VADProcessor = Depends(get_vad_processor),
):
    """批量处理多个音频片段的VAD检测
    
    参数:
        segments: 音频片段列表，每个片段是一个浮点数列表
        sample_rate: 采样率
        reset_between_segments: 是否在处理每个片段之间重置VAD状态
    
    返回:
        每个片段的VAD检测结果列表
    """
    start_time = time.time()
    results = []
    
    try:
        if not segments:
            raise ValidationError("音频片段列表不能为空")
        
        logger.info(
            "批量VAD检测请求",
            segment_count=len(segments),
            sample_rate=sample_rate,
            reset_between=reset_between_segments,
        )
        
        for i, segment in enumerate(segments):
            if reset_between_segments and i > 0:
                vad_processor.reset()
            
            # 处理每个片段
            try:
                result = await vad_processor.process(segment)
                
                segment_result = {
                    "segment_index": i,
                    "is_speaking": result.is_speaking,
                    "state": result.current_state,
                    "state_changed": result.state_changed,
                    "probability": round(result.probability, 4),
                    "rms": round(result.rms, 4),
                    "max_amplitude": round(result.max_amplitude, 4),
                    "silence_timeout": result.silence_timeout,
                    "duration_seconds": round(len(segment) / sample_rate, 2),
                }
                
                results.append(segment_result)
                
            except Exception as e:
                logger.error(f"处理片段 {i} 时出错", error=str(e))
                results.append({
                    "segment_index": i,
                    "error": str(e),
                    "is_speaking": None,
                    "state": "error",
                })
        
        # 统计信息
        speech_segments = sum(1 for r in results if r.get("is_speaking") == True)
        silence_segments = sum(1 for r in results if r.get("is_speaking") == False)
        error_segments = sum(1 for r in results if r.get("state") == "error")
        
        response = {
            "segments": results,
            "summary": {
                "total_segments": len(segments),
                "speech_segments": speech_segments,
                "silence_segments": silence_segments,
                "error_segments": error_segments,
                "speech_ratio": round(speech_segments / len(segments), 2) if segments else 0,
            },
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "metadata": {
                "sample_rate": sample_rate,
                "reset_between_segments": reset_between_segments,
                "vad_threshold": vad_processor.threshold,
            }
        }
        
        return response
        
    except ValidationError as e:
        logger.warning("验证错误", error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    
    except Exception as e:
        logger.exception("批量VAD处理时发生错误")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("/vad/analyze-file")
async def analyze_audio_file(
    audio_data: List[float],
    sample_rate: int = 16000,
    window_duration: float = 0.5,  # 窗口时长（秒）
    overlap: float = 0.1,  # 重叠时长（秒）
    vad_processor: VADProcessor = Depends(get_vad_processor),
):
    """分析整个音频文件的语音活动分布
    
    参数:
        audio_data: 完整音频文件的数据
        sample_rate: 采样率
        window_duration: 分析窗口时长（秒）
        overlap: 窗口重叠时长（秒）
    
    返回:
        音频文件的VAD分析结果，包括语音段时间戳
    """
    start_time = time.time()
    
    try:
        if not audio_data:
            raise ValidationError("音频数据不能为空")
        
        # 计算窗口参数
        window_size = int(window_duration * sample_rate)
        hop_size = int((window_duration - overlap) * sample_rate)
        
        if window_size > len(audio_data):
            raise ValidationError("窗口大小超过音频长度")
        
        logger.info(
            "音频文件VAD分析请求",
            audio_length=len(audio_data),
            duration_seconds=len(audio_data) / sample_rate,
            window_size=window_size,
            hop_size=hop_size,
        )
        
        # 重置VAD状态
        vad_processor.reset()
        
        # 分析音频
        speech_segments = []
        current_speech_start = None
        position = 0
        window_index = 0
        
        while position + window_size <= len(audio_data):
            # 提取窗口
            window = audio_data[position:position + window_size]
            
            # VAD检测
            result = await vad_processor.process(window)
            
            # 记录语音段
            timestamp = position / sample_rate
            
            if result.is_speaking and current_speech_start is None:
                # 语音段开始
                current_speech_start = timestamp
                
            elif not result.is_speaking and current_speech_start is not None:
                # 语音段结束
                speech_segments.append({
                    "start": round(current_speech_start, 2),
                    "end": round(timestamp, 2),
                    "duration": round(timestamp - current_speech_start, 2),
                })
                current_speech_start = None
            
            position += hop_size
            window_index += 1
        
        # 处理最后一个语音段
        if current_speech_start is not None:
            end_time = len(audio_data) / sample_rate
            speech_segments.append({
                "start": round(current_speech_start, 2),
                "end": round(end_time, 2),
                "duration": round(end_time - current_speech_start, 2),
            })
        
        # 计算统计信息
        total_duration = len(audio_data) / sample_rate
        total_speech_duration = sum(seg["duration"] for seg in speech_segments)
        
        response = {
            "speech_segments": speech_segments,
            "statistics": {
                "total_duration": round(total_duration, 2),
                "total_speech_duration": round(total_speech_duration, 2),
                "total_silence_duration": round(total_duration - total_speech_duration, 2),
                "speech_ratio": round(total_speech_duration / total_duration, 2) if total_duration > 0 else 0,
                "segment_count": len(speech_segments),
                "average_segment_duration": round(total_speech_duration / len(speech_segments), 2) if speech_segments else 0,
            },
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "metadata": {
                "sample_rate": sample_rate,
                "window_duration": window_duration,
                "overlap": overlap,
                "total_windows": window_index,
            }
        }
        
        logger.info(
            "音频文件VAD分析完成",
            segment_count=len(speech_segments),
            speech_ratio=response["statistics"]["speech_ratio"],
            processing_time_ms=response["processing_time_ms"],
        )
        
        return response
        
    except ValidationError as e:
        logger.warning("验证错误", error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    
    except Exception as e:
        logger.exception("音频文件VAD分析时发生错误")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.get("/vad/status")
async def get_vad_status(vad_processor: VADProcessor = Depends(get_vad_processor)):
    """获取VAD处理器当前状态和配置信息"""
    stats = vad_processor.get_stats()
    
    return {
        "status": "operational",
        "current_state": {
            "is_speaking": stats["is_speaking"],
            "use_real_vad": stats["use_real_vad"],
            "vad_type": "TEN-VAD" if stats["use_real_vad"] else "Energy-based",
        },
        "configuration": {
            "threshold": stats["threshold"],
            "silence_duration": stats["silence_duration"],
            "hop_size": stats["hop_size"],
        },
        "buffer_info": {
            "vad_buffer_size": stats["vad_buffer_size"],
        },
        "capabilities": {
            "ten_vad_available": stats["use_real_vad"],
            "supported_sample_rates": [8000, 16000, 22050, 44100, 48000],
            "min_audio_length": stats["hop_size"],
        }
    }


@router.post("/vad/reset")
async def reset_vad_state(vad_processor: VADProcessor = Depends(get_vad_processor)):
    """重置VAD处理器状态"""
    vad_processor.reset()
    
    return {
        "status": "success",
        "message": "VAD处理器已重置",
        "timestamp": int(time.time() * 1000),
    }