"""移动端专用 API 接口 - 针对 Expo React Native 优化"""

import base64
import io
import time
import tempfile
import subprocess
import os
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field
import structlog
import numpy as np
import soundfile as sf

from asr_api_service.config import settings
from asr_api_service.core.audio.vad import VADProcessor
from asr_api_service.exceptions import VADError, ValidationError
from asr_api_service.utils.validation import validate_audio_data

router = APIRouter()
logger = structlog.get_logger(__name__)


class MobileAudioRequest(BaseModel):
    """移动端音频请求模型"""
    audio_base64: str = Field(..., description="Base64 编码的音频数据")
    format: str = Field(..., description="音频格式: wav, m4a, mp3, webm 等")
    sample_rate: int = Field(16000, description="采样率")
    
    # VAD 参数
    enable_vad: bool = Field(True, description="是否启用 VAD 检测")
    vad_window_duration: float = Field(0.5, description="VAD 窗口时长（秒）")
    vad_overlap: float = Field(0.1, description="VAD 窗口重叠（秒）")
    
    # 处理选项
    return_format: str = Field("segments", description="返回格式: segments, merged, base64")
    compress_output: bool = Field(False, description="是否压缩输出音频")


class MobileAudioResponse(BaseModel):
    """移动端音频响应模型"""
    success: bool
    message: str
    
    # VAD 结果
    has_speech: bool = Field(..., description="是否检测到语音")
    speech_segments: List[Dict[str, float]] = Field(..., description="语音段列表")
    speech_ratio: float = Field(..., description="语音占比")
    total_duration: float = Field(..., description="总时长（秒）")
    
    # 音频数据
    audio_data: Optional[List[float]] = Field(None, description="处理后的音频数据（PCM）")
    audio_base64: Optional[str] = Field(None, description="Base64 编码的音频")
    audio_format: Optional[str] = Field(None, description="音频格式")
    
    # 性能指标
    processing_time_ms: int = Field(..., description="处理时间（毫秒）")
    audio_size_bytes: Optional[int] = Field(None, description="音频大小（字节）")


# 全局 VAD 处理器（复用）
_vad_processor: Optional[VADProcessor] = None


async def get_vad_processor() -> VADProcessor:
    """获取 VAD 处理器实例"""
    global _vad_processor
    if _vad_processor is None:
        _vad_processor = VADProcessor(
            threshold=settings.vad_threshold,
            silence_duration=settings.vad_silence_duration,
            hop_size=settings.vad_hop_size,
        )
    return _vad_processor


class AudioConverter:
    """音频格式转换工具"""
    
    @staticmethod
    def _check_ffmpeg_available() -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @staticmethod
    def _convert_with_ffmpeg(input_path: str, output_path: str, sample_rate: int = 16000) -> bool:
        """使用 ffmpeg 转换音频格式"""
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-ar', str(sample_rate),  # 设置采样率
                '-ac', '1',               # 转为单声道
                '-f', 'wav',              # 输出格式为 WAV
                '-y',                     # 覆盖输出文件
                output_path
            ]
            
            result = subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE, 
                check=True,
                text=True
            )
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg 转换失败: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"ffmpeg 调用异常: {e}")
            return False
    
    @staticmethod
    def base64_to_audio(audio_base64: str, format: str) -> tuple[np.ndarray, int]:
        """
        将 Base64 音频转换为 NumPy 数组
        
        返回: (音频数据, 采样率)
        """
        try:
            # 解码 Base64
            audio_bytes = base64.b64decode(audio_base64)
            
            # soundfile 原生支持的格式
            native_formats = ['wav', 'flac', 'ogg']
            
            if format.lower() in native_formats:
                # 使用 soundfile 直接读取
                try:
                    with io.BytesIO(audio_bytes) as audio_io:
                        audio_data, sample_rate = sf.read(audio_io)
                except Exception as e:
                    logger.warning(f"soundfile 读取失败，尝试 ffmpeg: {e}")
                    # 如果 soundfile 失败，也尝试 ffmpeg
                    return AudioConverter._convert_with_ffmpeg_fallback(
                        audio_bytes, format
                    )
            else:
                # 对于其他格式（如 m4a, mp3），使用 ffmpeg
                return AudioConverter._convert_with_ffmpeg_fallback(
                    audio_bytes, format
                )
            
            # 确保是单声道
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            
            # 归一化到 [-1, 1]
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                audio_data = audio_data / max_val
            
            return audio_data.astype(np.float32), sample_rate
            
        except Exception as e:
            logger.error(f"音频转换失败: {e}")
            raise ValueError(f"无法转换音频格式 {format}: {str(e)}")
    
    @staticmethod
    def _convert_with_ffmpeg_fallback(audio_bytes: bytes, format: str) -> tuple[np.ndarray, int]:
        """使用 ffmpeg 作为后备转换方案"""
        # 检查 ffmpeg 是否可用
        if not AudioConverter._check_ffmpeg_available():
            raise ValueError(
                f"不支持的音频格式 {format}。"
                f"请安装 ffmpeg 以支持更多格式，或使用 WAV/FLAC/OGG 格式。"
            )
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=f'.{format}', delete=False) as input_file:
            input_file.write(audio_bytes)
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # 使用 ffmpeg 转换
            success = AudioConverter._convert_with_ffmpeg(input_path, output_path)
            
            if not success:
                raise ValueError(f"ffmpeg 无法转换 {format} 格式")
            
            # 读取转换后的 WAV 文件
            audio_data, sample_rate = sf.read(output_path)
            
            # 确保是单声道
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            
            # 归一化到 [-1, 1]
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                audio_data = audio_data / max_val
            
            return audio_data.astype(np.float32), sample_rate
            
        finally:
            # 清理临时文件
            try:
                os.unlink(input_path)
                os.unlink(output_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")
    
    @staticmethod
    def audio_to_base64(audio_data: np.ndarray, sample_rate: int, format: str = 'wav') -> str:
        """
        将音频数据转换为 Base64
        
        参数:
            audio_data: 音频数据（-1 到 1 的浮点数）
            sample_rate: 采样率
            format: 输出格式
        """
        try:
            # 创建内存缓冲区
            buffer = io.BytesIO()
            
            # 写入音频数据
            sf.write(buffer, audio_data, sample_rate, format=format)
            
            # 获取字节数据
            audio_bytes = buffer.getvalue()
            
            # 编码为 Base64
            return base64.b64encode(audio_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"音频编码失败: {e}")
            raise ValueError(f"无法编码音频: {str(e)}")
    
    @staticmethod
    def resample_audio(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        重采样音频数据
        
        简单的线性插值重采样，适用于语音
        """
        if orig_sr == target_sr:
            return audio_data
        
        # 计算重采样因子
        factor = target_sr / orig_sr
        
        # 计算新长度
        new_length = int(len(audio_data) * factor)
        
        # 使用线性插值
        old_indices = np.arange(len(audio_data))
        new_indices = np.linspace(0, len(audio_data) - 1, new_length)
        
        return np.interp(new_indices, old_indices, audio_data)


@router.post("/mobile/process-audio-efficient")
async def process_mobile_audio_efficient(
    audio: UploadFile = File(..., description="音频文件（直接上传，无Base64编码）"),
    sample_rate: int = Form(16000, description="采样率"),
    enable_vad: bool = Form(True, description="是否启用VAD检测"),
    return_audio: bool = Form(False, description="是否返回处理后的音频"),
    output_format: str = Form("json", description="输出格式: json, binary")
):
    """
    高效音频处理接口 - 避免Base64编码
    
    优势:
    - 直接文件上传，无Base64膨胀
    - 可选择返回音频数据
    - 支持二进制响应格式
    - 内存使用更少，处理更快
    """
    start_time = time.time()
    
    try:
        # 读取音频文件
        content = await audio.read()
        format_ext = audio.filename.split('.')[-1].lower() if audio.filename else 'wav'
        
        logger.info(
            "高效音频处理请求",
            filename=audio.filename,
            format=format_ext,
            file_size=len(content),
            return_audio=return_audio
        )
        
        # 直接转换音频（避免Base64编码步骤）
        audio_data = None
        actual_sample_rate = sample_rate
        
        # 根据格式直接处理
        native_formats = ['wav', 'flac', 'ogg']
        
        if format_ext.lower() in native_formats:
            # 使用soundfile直接读取
            try:
                with io.BytesIO(content) as audio_io:
                    audio_data, actual_sample_rate = sf.read(audio_io)
            except Exception as e:
                logger.warning(f"soundfile直接读取失败，使用ffmpeg: {e}")
                audio_data, actual_sample_rate = AudioConverter._convert_with_ffmpeg_fallback(content, format_ext)
        else:
            # 使用ffmpeg处理其他格式
            audio_data, actual_sample_rate = AudioConverter._convert_with_ffmpeg_fallback(content, format_ext)
        
        # 确保是单声道和正确的数据类型
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)
        
        # 归一化
        max_val = np.abs(audio_data).max()
        if max_val > 0:
            audio_data = audio_data / max_val
        
        audio_data = audio_data.astype(np.float32)
        
        # 重采样
        if actual_sample_rate != sample_rate:
            audio_data = AudioConverter.resample_audio(audio_data, actual_sample_rate, sample_rate)
        
        # VAD处理
        speech_segments = []
        valid_audio = audio_data
        
        if enable_vad:
            vad_processor = await get_vad_processor()
            segments_result = await analyze_audio_with_vad(
                audio_data, sample_rate, 0.5, 0.1, vad_processor
            )
            speech_segments = segments_result['speech_segments']
            
            if speech_segments:
                valid_audio = extract_segments(audio_data, speech_segments, sample_rate)
            else:
                valid_audio = np.array([], dtype=np.float32)
        
        # 构建响应
        total_duration = len(audio_data) / sample_rate
        response_data = {
            "success": True,
            "message": "音频处理成功",
            "has_speech": len(speech_segments) > 0,
            "speech_segments": speech_segments,
            "speech_ratio": sum(s['duration'] for s in speech_segments) / total_duration if total_duration > 0 else 0,
            "total_duration": round(total_duration, 2),
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "efficiency_note": "使用直接文件上传，避免Base64编码"
        }
        
        # 可选返回音频数据
        if return_audio and len(valid_audio) > 0:
            if output_format == "binary":
                # 返回二进制音频数据
                from fastapi.responses import Response
                audio_bytes = valid_audio.astype(np.float32).tobytes()
                return Response(
                    content=audio_bytes,
                    media_type="application/octet-stream",
                    headers={
                        "X-Audio-Info": json.dumps(response_data),
                        "X-Sample-Rate": str(sample_rate),
                        "X-Samples": str(len(valid_audio)),
                        "X-Duration": str(len(valid_audio) / sample_rate)
                    }
                )
            else:
                # JSON格式，但只返回必要信息
                response_data["audio_samples"] = len(valid_audio)
                response_data["audio_duration"] = len(valid_audio) / sample_rate
                # 不返回完整音频数据，只返回统计信息
        
        return response_data
        
    except Exception as e:
        logger.exception("高效音频处理失败")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.post("/mobile/process-audio", response_model=MobileAudioResponse)
async def process_mobile_audio(request: MobileAudioRequest):
    """
    移动端音频处理接口 - 一站式处理音频录制结果
    
    功能:
    1. 自动转换各种音频格式
    2. VAD 检测提取有效语音
    3. 返回处理后的音频数据
    
    支持的格式: wav, m4a, mp3, ogg, webm, flac
    """
    start_time = time.time()
    
    try:
        logger.info(
            "移动端音频处理请求",
            format=request.format,
            sample_rate=request.sample_rate,
            enable_vad=request.enable_vad,
            audio_size=len(request.audio_base64),
        )
        
        # 步骤1: 转换音频格式
        audio_conversion_start = time.time()
        audio_data, actual_sample_rate = AudioConverter.base64_to_audio(
            request.audio_base64,
            request.format
        )
        audio_conversion_time = int((time.time() - audio_conversion_start) * 1000)
        
        logger.info(
            "音频格式转换完成",
            format=request.format,
            original_sample_rate=actual_sample_rate,
            target_sample_rate=request.sample_rate,
            audio_length=len(audio_data),
            conversion_time_ms=audio_conversion_time,
        )
        
        # 步骤2: 重采样（如果需要）
        if actual_sample_rate != request.sample_rate:
            logger.info(f"重采样: {actual_sample_rate} -> {request.sample_rate}")
            resample_start = time.time()
            audio_data = AudioConverter.resample_audio(
                audio_data,
                actual_sample_rate,
                request.sample_rate
            )
            resample_time = int((time.time() - resample_start) * 1000)
            logger.info(f"重采样完成，耗时: {resample_time}ms")
        
        # 计算原始音频信息
        total_duration = len(audio_data) / request.sample_rate
        
        # 音频质量分析
        rms_level = float(np.sqrt(np.mean(audio_data ** 2)))
        peak_level = float(np.max(np.abs(audio_data)))
        
        logger.info(
            "音频质量分析",
            duration=total_duration,
            rms_level=rms_level,
            peak_level=peak_level,
            samples_count=len(audio_data),
        )
        
        # 步骤3: VAD 检测（如果启用）
        speech_segments = []
        valid_audio = audio_data
        
        if request.enable_vad:
            vad_processor = await get_vad_processor()
            
            # 分析音频文件
            segments_result = await analyze_audio_with_vad(
                audio_data,
                request.sample_rate,
                request.vad_window_duration,
                request.vad_overlap,
                vad_processor
            )
            
            speech_segments = segments_result['speech_segments']
            
            # 提取有效音频段
            if speech_segments:
                valid_audio = extract_segments(
                    audio_data,
                    speech_segments,
                    request.sample_rate
                )
            else:
                valid_audio = np.array([], dtype=np.float32)
        
        # 步骤4: 准备响应数据
        response_data = {
            "success": True,
            "message": "音频处理成功",
            "has_speech": len(speech_segments) > 0,
            "speech_segments": speech_segments,
            "speech_ratio": sum(s['duration'] for s in speech_segments) / total_duration if total_duration > 0 else 0,
            "total_duration": round(total_duration, 2),
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }
        
        # 根据返回格式处理音频数据
        if request.return_format == "segments":
            # 返回 PCM 数组
            response_data["audio_data"] = valid_audio.tolist()
            response_data["audio_format"] = "pcm_f32"
            
        elif request.return_format == "base64":
            # 返回 Base64 编码的音频
            output_format = 'wav'
            if request.compress_output:
                # 可以使用其他格式压缩，如 flac
                output_format = 'flac'
            
            audio_base64 = AudioConverter.audio_to_base64(
                valid_audio,
                request.sample_rate,
                output_format
            )
            response_data["audio_base64"] = audio_base64
            response_data["audio_format"] = output_format
            response_data["audio_size_bytes"] = len(base64.b64decode(audio_base64))
            
        elif request.return_format == "merged":
            # 返回合并的音频数据和 Base64
            response_data["audio_data"] = valid_audio.tolist()
            response_data["audio_base64"] = AudioConverter.audio_to_base64(
                valid_audio,
                request.sample_rate,
                'wav'
            )
            response_data["audio_format"] = "wav"
        
        logger.info(
            "音频处理完成",
            has_speech=response_data["has_speech"],
            speech_segments_count=len(speech_segments),
            speech_ratio=response_data["speech_ratio"],
            processing_time_ms=response_data["processing_time_ms"],
        )
        
        return MobileAudioResponse(**response_data)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("移动端音频处理失败")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.post("/mobile/quick-vad")
async def quick_vad_check(
    audio_base64: str = Form(...),
    format: str = Form(...),
    sample_rate: int = Form(16000),
):
    """
    快速 VAD 检测接口 - 仅返回是否包含语音
    
    适用于快速预检，响应极快
    """
    start_time = time.time()
    
    try:
        # 转换音频
        audio_data, _ = AudioConverter.base64_to_audio(audio_base64, format)
        
        # 快速 VAD 检测（只检测前几秒）
        max_duration = 5.0  # 最多检测5秒
        max_samples = int(sample_rate * max_duration)
        
        if len(audio_data) > max_samples:
            audio_data = audio_data[:max_samples]
        
        # 简单的能量检测
        rms = np.sqrt(np.mean(audio_data ** 2))
        has_speech = rms > 0.01  # 简单阈值
        
        # 如果需要更准确的检测
        if has_speech and settings.vad_threshold > 0:
            vad_processor = await get_vad_processor()
            vad_result = await vad_processor.process(audio_data.tolist())
            has_speech = vad_result.is_speaking
        
        return {
            "has_speech": has_speech,
            "rms": float(rms),
            "duration": len(audio_data) / sample_rate,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }
        
    except Exception as e:
        logger.error(f"快速 VAD 检测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mobile/quick-vad-file")
async def quick_vad_check_file(
    audio: UploadFile = File(..., description="音频文件"),
    sample_rate: int = Form(16000, description="采样率"),
):
    """
    快速 VAD 检测接口（文件上传版）- 适用于 Swagger UI 测试
    
    仅返回是否包含语音，响应极快
    """
    start_time = time.time()
    
    try:
        # 读取上传的文件
        content = await audio.read()
        
        # 获取文件格式
        filename = audio.filename or "audio"
        format_ext = filename.split('.')[-1].lower() if '.' in filename else 'wav'
        
        # 转换为 Base64
        audio_base64 = base64.b64encode(content).decode('utf-8')
        
        logger.info(
            "快速 VAD 文件检测",
            filename=filename,
            format=format_ext,
            file_size=len(content),
        )
        
        # 转换音频
        audio_data, _ = AudioConverter.base64_to_audio(audio_base64, format_ext)
        
        # 快速 VAD 检测（只检测前几秒）
        max_duration = 5.0  # 最多检测5秒
        max_samples = int(sample_rate * max_duration)
        
        if len(audio_data) > max_samples:
            audio_data = audio_data[:max_samples]
        
        # 简单的能量检测
        rms = np.sqrt(np.mean(audio_data ** 2))
        has_speech = rms > 0.01  # 简单阈值
        
        # 如果需要更准确的检测
        if has_speech and settings.vad_threshold > 0:
            vad_processor = await get_vad_processor()
            vad_result = await vad_processor.process(audio_data.tolist())
            has_speech = vad_result.is_speaking
        
        return {
            "filename": filename,
            "format": format_ext,
            "file_size": len(content),
            "has_speech": has_speech,
            "rms": float(rms),
            "duration": len(audio_data) / sample_rate,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }
        
    except Exception as e:
        logger.error(f"快速 VAD 文件检测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mobile/batch-process")
async def batch_process_audio(
    audio_files: List[UploadFile] = File(...),
    enable_vad: bool = Form(True),
    merge_results: bool = Form(False),
):
    """
    批量处理音频文件
    
    适用于一次上传多个音频片段
    """
    start_time = time.time()
    results = []
    all_valid_audio = []
    
    try:
        vad_processor = await get_vad_processor() if enable_vad else None
        
        for i, audio_file in enumerate(audio_files):
            # 读取文件
            content = await audio_file.read()
            
            # 检测格式
            format = audio_file.filename.split('.')[-1].lower()
            
            # 转换为 Base64
            audio_base64 = base64.b64encode(content).decode('utf-8')
            
            # 处理单个文件
            try:
                # 转换音频
                audio_data, sample_rate = AudioConverter.base64_to_audio(audio_base64, format)
                
                result = {
                    "index": i,
                    "filename": audio_file.filename,
                    "duration": len(audio_data) / sample_rate,
                }
                
                if enable_vad:
                    # VAD 分析
                    segments_result = await analyze_audio_with_vad(
                        audio_data,
                        sample_rate,
                        0.5,
                        0.1,
                        vad_processor
                    )
                    
                    result["speech_segments"] = segments_result['speech_segments']
                    result["has_speech"] = len(segments_result['speech_segments']) > 0
                    
                    # 提取有效音频
                    if result["has_speech"]:
                        valid_audio = extract_segments(
                            audio_data,
                            segments_result['speech_segments'],
                            sample_rate
                        )
                        all_valid_audio.append(valid_audio)
                else:
                    result["has_speech"] = True
                    all_valid_audio.append(audio_data)
                
                result["success"] = True
                
            except Exception as e:
                result = {
                    "index": i,
                    "filename": audio_file.filename,
                    "success": False,
                    "error": str(e),
                }
            
            results.append(result)
        
        # 准备响应
        response = {
            "results": results,
            "total_files": len(audio_files),
            "successful": sum(1 for r in results if r.get("success", False)),
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }
        
        # 如果需要合并结果
        if merge_results and all_valid_audio:
            merged_audio = np.concatenate(all_valid_audio)
            
            # 转换为 Base64
            merged_base64 = AudioConverter.audio_to_base64(
                merged_audio,
                16000,  # 假设统一采样率
                'wav'
            )
            
            response["merged_audio"] = {
                "audio_base64": merged_base64,
                "format": "wav",
                "duration": len(merged_audio) / 16000,
                "size_bytes": len(base64.b64decode(merged_base64)),
            }
        
        return response
        
    except Exception as e:
        logger.exception("批量处理失败")
        raise HTTPException(status_code=500, detail=str(e))


# 辅助函数

async def analyze_audio_with_vad(
    audio_data: np.ndarray,
    sample_rate: int,
    window_duration: float,
    overlap: float,
    vad_processor: VADProcessor
) -> Dict[str, Any]:
    """
    使用 VAD 分析音频数据
    
    返回语音段信息
    """
    # 计算窗口参数
    window_size = int(window_duration * sample_rate)
    hop_size = int((window_duration - overlap) * sample_rate)
    
    # 重置 VAD 状态
    vad_processor.reset()
    
    # 分析音频
    speech_segments = []
    current_speech_start = None
    position = 0
    
    while position + window_size <= len(audio_data):
        # 提取窗口
        window = audio_data[position:position + window_size]
        
        # VAD 检测
        result = await vad_processor.process(window.tolist())
        
        # 记录语音段
        timestamp = position / sample_rate
        
        if result.is_speaking and current_speech_start is None:
            # 语音开始
            current_speech_start = timestamp
            
        elif not result.is_speaking and current_speech_start is not None:
            # 语音结束
            speech_segments.append({
                "start": round(current_speech_start, 2),
                "end": round(timestamp, 2),
                "duration": round(timestamp - current_speech_start, 2),
            })
            current_speech_start = None
        
        position += hop_size
    
    # 处理最后一个语音段
    if current_speech_start is not None:
        end_time = len(audio_data) / sample_rate
        speech_segments.append({
            "start": round(current_speech_start, 2),
            "end": round(end_time, 2),
            "duration": round(end_time - current_speech_start, 2),
        })
    
    return {
        "speech_segments": speech_segments,
        "total_duration": len(audio_data) / sample_rate,
    }


def extract_segments(
    audio_data: np.ndarray,
    segments: List[Dict[str, float]],
    sample_rate: int
) -> np.ndarray:
    """
    提取音频中的有效片段
    
    参数:
        audio_data: 完整音频数据
        segments: 语音段列表
        sample_rate: 采样率
    
    返回:
        合并后的有效音频
    """
    valid_chunks = []
    
    for segment in segments:
        start_sample = int(segment['start'] * sample_rate)
        end_sample = int(segment['end'] * sample_rate)
        
        # 确保索引有效
        start_sample = max(0, start_sample)
        end_sample = min(len(audio_data), end_sample)
        
        if start_sample < end_sample:
            chunk = audio_data[start_sample:end_sample]
            valid_chunks.append(chunk)
    
    if valid_chunks:
        return np.concatenate(valid_chunks)
    else:
        return np.array([], dtype=np.float32)


@router.post("/mobile/process-audio-file", response_model=MobileAudioResponse)
async def process_mobile_audio_file(
    audio: UploadFile = File(..., description="音频文件"),
    sample_rate: int = Form(16000, description="采样率"),
    enable_vad: bool = Form(True, description="是否启用 VAD 检测"),
    vad_window_duration: float = Form(0.5, description="VAD 窗口时长（秒）"),
    vad_overlap: float = Form(0.1, description="VAD 窗口重叠（秒）"),
    return_format: str = Form("segments", description="返回格式: segments, base64, merged"),
    compress_output: bool = Form(False, description="是否压缩输出音频"),
):
    """
    处理上传的音频文件 - 适用于 Swagger UI 测试
    
    这个端点与 process_mobile_audio 功能相同，但接受文件上传而不是 Base64。
    
    支持的格式: wav, m4a, mp3, ogg, webm, flac
    """
    start_time = time.time()
    
    try:
        # 读取上传的文件
        content = await audio.read()
        
        # 获取文件格式
        filename = audio.filename or "audio"
        format_ext = filename.split('.')[-1].lower() if '.' in filename else 'wav'
        
        # 转换为 Base64
        audio_base64 = base64.b64encode(content).decode('utf-8')
        
        logger.info(
            "移动端音频文件处理请求",
            filename=filename,
            format=format_ext,
            file_size=len(content),
            sample_rate=sample_rate,
            enable_vad=enable_vad,
        )
        
        # 创建请求对象
        request = MobileAudioRequest(
            audio_base64=audio_base64,
            format=format_ext,
            sample_rate=sample_rate,
            enable_vad=enable_vad,
            vad_window_duration=vad_window_duration,
            vad_overlap=vad_overlap,
            return_format=return_format,
            compress_output=compress_output,
        )
        
        # 调用主处理函数
        return await process_mobile_audio(request)
        
    except Exception as e:
        logger.exception("处理音频文件失败")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/mobile/health")
async def mobile_health_check():
    """移动端 API 健康检查"""
    # 检查 ffmpeg 可用性
    ffmpeg_available = AudioConverter._check_ffmpeg_available()
    
    # 根据 ffmpeg 可用性确定支持的格式
    native_formats = ["wav", "flac", "ogg"]
    extended_formats = ["m4a", "mp3", "webm", "aac"] if ffmpeg_available else []
    supported_formats = native_formats + extended_formats
    
    return {
        "status": "healthy",
        "features": {
            "audio_conversion": True,
            "vad_detection": True,
            "batch_processing": True,
            "file_upload": True,
            "ffmpeg_available": ffmpeg_available,
            "supported_formats": supported_formats,
        },
        "format_support": {
            "native": native_formats,
            "extended": extended_formats,
            "total": len(supported_formats),
        },
        "vad_config": {
            "threshold": settings.vad_threshold,
            "silence_duration": settings.vad_silence_duration,
        },
        "endpoints": {
            "process_audio": "/api/v1/mobile/process-audio",
            "process_audio_file": "/api/v1/mobile/process-audio-file",
            "quick_vad": "/api/v1/mobile/quick-vad",
            "quick_vad_file": "/api/v1/mobile/quick-vad-file",
            "batch_process": "/api/v1/mobile/batch-process",
        },
        "recommendations": {
            "install_ffmpeg": not ffmpeg_available,
            "preferred_formats": ["wav", "flac"] if not ffmpeg_available else ["wav", "m4a", "mp3"],
        },
        "timestamp": int(time.time()),
    }