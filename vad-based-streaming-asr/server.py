#!/usr/bin/env python3
"""
VAD-Based Streaming ASR Server
实时音频流处理服务器，支持VAD检测和Whisper语音识别
"""

import os
os.environ['https_proxy'] = 'http://127.0.0.1:7890'
os.environ['http_proxy'] = 'http://127.0.0.1:7890'

import asyncio
import json
import websockets
import numpy as np
import requests
import time
import wave
import tempfile
import logging
import sys
from datetime import datetime
import shutil

# 添加父目录到Python路径，以便导入ten_vad
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioBuffer:
    """音频缓冲区管理"""
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.buffer = []
        self.start_time = time.time()
        
    def append(self, audio_data):
        """添加音频数据到缓冲区"""
        self.buffer.extend(audio_data)
        
    def get_duration(self):
        """获取缓冲区音频时长（秒）"""
        return len(self.buffer) / self.sample_rate
        
    def extract_segment(self, duration=None, start_index=0):
        """提取音频片段
        Args:
            duration: 持续时间（秒），None表示提取全部
            start_index: 开始位置的采样点索引
        """
        if start_index < 0 or start_index > len(self.buffer):
            start_index = 0
            
        if duration is None:
            segment = self.buffer[start_index:].copy()
            self.buffer = self.buffer[:start_index]  # 保留start_index之前的数据
        else:
            samples = int(duration * self.sample_rate)
            end_index = min(start_index + samples, len(self.buffer))
            segment = self.buffer[start_index:end_index]
            # 不自动清理buffer，由调用者决定
        return segment
    
    def get_buffer_length(self):
        """获取缓冲区采样点数量"""
        return len(self.buffer)
        
    def clear(self):
        """清空缓冲区"""
        self.buffer.clear()

class TenVADProcessor:
    """TEN-VAD处理器"""
    def __init__(self, threshold=0.35, silence_duration=0.8):
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.is_speaking = False
        self.silence_start = None
        self.debug_counter = 0
        self.vad_history_dir = os.path.join(os.path.dirname(__file__), 'log', 'vad')
        
        # 创建目录
        os.makedirs(self.vad_history_dir, exist_ok=True)
        
        # 导入并初始化TEN-VAD
        try:
            # 添加ten-vad路径到Python路径
            ten_vad_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ten-vad', 'include')
            if ten_vad_path not in sys.path:
                sys.path.insert(0, ten_vad_path)
            
            from ten_vad import TenVad
            self.hop_size = 256  # 16ms @ 16kHz
            self.ten_vad = TenVad(hop_size=self.hop_size, threshold=self.threshold)
            self.use_real_vad = True
            logger.info(f"TEN-VAD initialized with hop_size={self.hop_size}, threshold={self.threshold}")
        except Exception as e:
            logger.warning(f"Failed to initialize TEN-VAD, falling back to simple VAD: {str(e)}")
            self.use_real_vad = False
            self.ten_vad = None
        
    async def process(self, audio_data):
        """处理音频数据，返回VAD状态"""
        audio_array = np.array(audio_data)
        
        # 计算音量指标（用于日志记录）
        rms = np.sqrt(np.mean(audio_array ** 2))
        max_amplitude = np.max(np.abs(audio_array))
        
        if self.use_real_vad and self.ten_vad:
            # 使用真正的TEN-VAD
            # TEN-VAD需要int16格式的音频数据，每次处理hop_size个样本
            # 转换float32到int16
            audio_int16 = (audio_array * 32767).astype(np.int16)
            
            # TEN-VAD需要恰好hop_size个样本
            # 如果数据不够，先存储起来
            if not hasattr(self, 'vad_buffer'):
                self.vad_buffer = []
            
            self.vad_buffer.extend(audio_int16)
            
            # 默认结果
            probability = 0.0
            voice_flag = 0
            
            # 处理所有完整的帧
            while len(self.vad_buffer) >= self.hop_size:
                # 提取一帧数据
                frame = np.array(self.vad_buffer[:self.hop_size], dtype=np.int16)
                self.vad_buffer = self.vad_buffer[self.hop_size:]
                
                try:
                    # 调用TEN-VAD处理
                    probability, voice_flag = self.ten_vad.process(frame)
                except Exception as e:
                    logger.error(f"TEN-VAD process error: {str(e)}")
                    # 降级到简单VAD
                    voice_flag = 1 if rms > 0.01 else 0
                    probability = rms
            
            current_speaking = (voice_flag == 1)
            
            # 调试信息
            self.debug_counter += 1
            if self.debug_counter % 10 == 0:
                logger.info(f"TEN-VAD Debug - Probability: {probability:.4f}, Flag: {voice_flag}, RMS: {rms:.6f}, Speaking: {current_speaking}")
        else:
            # 使用简单的基于音量的VAD
            current_speaking = rms > 0.01  # 使用固定的低阈值
            probability = rms
            
            # 调试信息
            self.debug_counter += 1
            if self.debug_counter % 10 == 0:
                logger.info(f"Simple VAD Debug - RMS: {rms:.6f}, Max: {max_amplitude:.6f}, Speaking: {current_speaking}")
        
        state_changed = current_speaking != self.is_speaking
        
        result = {
            'is_speaking': current_speaking,
            'state_changed': state_changed,
            'current_state': 'speech' if current_speaking else 'silence',
            'rms': rms,
            'max_amplitude': max_amplitude,
            'probability': probability if self.use_real_vad else rms
        }
        
        # 更新状态
        if state_changed:
            logger.info(f"VAD state changed: {'Speech' if current_speaking else 'Silence'}")
            
            # 保存VAD状态变化日志
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                log_data = {
                    'timestamp': timestamp,
                    'state': 'speech' if current_speaking else 'silence',
                    'previous_state': 'silence' if current_speaking else 'speech',
                    'rms': float(rms),
                    'max_amplitude': float(max_amplitude),
                    'threshold': self.threshold,
                    'probability': float(result.get('probability', 0)),
                    'vad_type': 'ten-vad' if self.use_real_vad else 'simple'
                }
                
                log_filename = f"{timestamp}.json"
                log_path = os.path.join(self.vad_history_dir, log_filename)
                
                with open(log_path, 'w', encoding='utf-8') as f:
                    json.dump(log_data, f, ensure_ascii=False, indent=2)
                    
                logger.info(f"Saved VAD state change: {log_filename}")
            except Exception as e:
                logger.error(f"Failed to save VAD log: {str(e)}")
            
            if not current_speaking:
                self.silence_start = time.time()
            else:
                self.silence_start = None
                
        self.is_speaking = current_speaking
        
        # 检查静音持续时间
        if self.silence_start and (time.time() - self.silence_start) >= self.silence_duration:
            result['silence_timeout'] = True
            
        return result

class WhisperClient:
    """Whisper ASR客户端"""
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://audio-prod.us-virginia-1.direct.fireworks.ai/v1/audio/transcriptions"
        self.asr_history_dir = os.path.join(os.path.dirname(__file__), 'log', 'asr')
        
        # 创建目录
        os.makedirs(self.asr_history_dir, exist_ok=True)
    
    async def test_network_connectivity(self):
        """测试网络连通性"""
        results = []
        
        # 测试Google连接
        try:
            response = requests.get('https://www.google.com', timeout=5)
            if response.status_code == 200:
                results.append(("Google", True, "连接成功"))
            else:
                results.append(("Google", False, f"状态码: {response.status_code}"))
        except requests.exceptions.Timeout:
            results.append(("Google", False, "连接超时"))
        except Exception as e:
            results.append(("Google", False, f"连接失败: {str(e)}"))
        
        # 测试Fireworks连接
        try:
            response = requests.get('https://api.fireworks.ai', timeout=5)
            if response.status_code in [200, 401, 403]:  # 401/403也说明能连接到服务器
                results.append(("Fireworks", True, "连接成功"))
            else:
                results.append(("Fireworks", False, f"状态码: {response.status_code}"))
        except requests.exceptions.Timeout:
            results.append(("Fireworks", False, "连接超时"))
        except Exception as e:
            results.append(("Fireworks", False, f"连接失败: {str(e)}"))
        
        return results
        
    async def test_connection(self):
        """测试API连接"""
        try:
            # 创建一个1秒的静音测试音频
            sample_rate = 16000
            duration = 1.0
            samples = int(sample_rate * duration)
            
            # 生成静音音频
            audio_data = np.zeros(samples)
            
            # 创建临时WAV文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                wav_path = tmp_file.name
                
                with wave.open(wav_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                    wav_file.writeframes(audio_int16.tobytes())
            
            # 测试API调用
            data_payload = {
                "model": "whisper-v3",
                "vad_model": "silero",
                "temperature": "0.0",
                "response_format": "json"
            }
            
            with open(wav_path, "rb") as f:
                response = requests.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": f},
                    data=data_payload,
                    timeout=10
                )
            
            os.unlink(wav_path)
            
            if response.status_code == 200:
                return True, "API连接成功"
            else:
                return False, f"API错误: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "API请求超时"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
        
    async def transcribe(self, audio_data, prompt=""):
        """调用Whisper API进行转录"""
        request_start_time = time.time()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        
        try:
            # 创建WAV文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                wav_path = tmp_file.name
                
                # 写入WAV文件
                with wave.open(wav_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    
                    # 确保audio_data是numpy数组，然后转换为int16
                    if not isinstance(audio_data, np.ndarray):
                        audio_data = np.array(audio_data, dtype=np.float32)
                    
                    # 限制范围到[-1, 1]以避免溢出
                    audio_data = np.clip(audio_data, -1.0, 1.0)
                    
                    # 转换为int16
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                    wav_file.writeframes(audio_int16.tobytes())
            
            # 准备API请求
            data_payload = {
                "model": "whisper-v3",
                "vad_model": "silero",
                "temperature": "0.0",
                "timestamp_granularities": "segment",
                "response_format": "verbose_json",
                "prompt": prompt
            }
            
            # 发送请求
            with open(wav_path, "rb") as f:
                response = requests.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": f},
                    data=data_payload,
                )
                
            # 计算请求时延
            request_duration = time.time() - request_start_time
            
            # 保存音频文件到历史
            try:
                saved_audio_path = os.path.join(self.asr_history_dir, f"{timestamp}.wav")
                shutil.copy(wav_path, saved_audio_path)
                logger.info(f"Saved ASR audio: {timestamp}.wav")
            except Exception as e:
                logger.error(f"Failed to save ASR audio: {str(e)}")
                
            # 清理临时文件
            os.unlink(wav_path)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    # Fireworks API 返回的格式可能是 {"text": "..."}
                    text = result.get('text', '')
                    if not text and 'segments' in result:
                        # 备用：从segments中提取文本
                        segments = result.get('segments', [])
                        text = ' '.join(seg.get('text', '') for seg in segments)
                    logger.info(f"Transcription successful, length: {len(text)}")
                    
                    # 保存ASR日志
                    try:
                        log_data = {
                            'timestamp': timestamp,
                            'request_duration_ms': int(request_duration * 1000),
                            'text': text,
                            'text_length': len(text),
                            'prompt': prompt,
                            'audio_file': f"{timestamp}.wav"
                        }
                        log_path = os.path.join(self.asr_history_dir, f"{timestamp}.json")
                        with open(log_path, 'w', encoding='utf-8') as f:
                            json.dump(log_data, f, ensure_ascii=False, indent=2)
                        logger.info(f"Saved ASR log: {timestamp}.json")
                    except Exception as e:
                        logger.error(f"Failed to save ASR log: {str(e)}")
                    
                    return text
                except Exception as e:
                    logger.error(f"Error parsing Whisper response: {str(e)}")
                    return ""
            else:
                # 避免记录可能很大的响应体
                error_msg = f"Whisper API error: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail.get('error', 'Unknown error')}"
                except:
                    # 如果无法解析JSON，只记录状态码
                    pass
                logger.error(error_msg)
                
                # 保存错误日志
                try:
                    log_data = {
                        'timestamp': timestamp,
                        'request_duration_ms': int(request_duration * 1000),
                        'error': error_msg,
                        'status_code': response.status_code,
                        'prompt': prompt,
                        'audio_file': f"{timestamp}.wav"
                    }
                    log_path = os.path.join(self.asr_history_dir, f"{timestamp}_error.json")
                    with open(log_path, 'w', encoding='utf-8') as f:
                        json.dump(log_data, f, ensure_ascii=False, indent=2)
                except:
                    pass
                    
                return ""
                
        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            
            # 保存异常日志
            try:
                log_data = {
                    'timestamp': timestamp,
                    'request_duration_ms': int((time.time() - request_start_time) * 1000),
                    'exception': str(e),
                    'prompt': prompt
                }
                log_path = os.path.join(self.asr_history_dir, f"{timestamp}_exception.json")
                with open(log_path, 'w', encoding='utf-8') as f:
                    json.dump(log_data, f, ensure_ascii=False, indent=2)
            except:
                pass
                
            return ""

class LLMProcessor:
    """LLM文本修正处理器"""
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.fireworks.ai/inference/v1/chat/completions"
        self.model = "accounts/fireworks/models/kimi-k2-instruct"
        
    async def correct(self, text):
        """使用LLM修正ASR文本"""
        if not text or not text.strip():
            return text
            
        prompt = f"""角色：
你是一名专业的ASR（自动语音识别）后处理专家。

核心原则：
1. 专注修正，而非改写：你的唯一任务是修正ASR系统因发音相似、口音、语速过快等因素导致的识别错误。对于原文中语义通顺、语法正确的部分，必须保持原样，不得进行任何同义词替换、语序调整或句式改写。
2. 上下文感知与逻辑判断：当一个词语在当前语境下显得突兀、不合逻辑时（例如，在技术讨论中出现一个毫不相关的日常词汇），应优先判断它是一个由发音相似词语造成的识别错误。
3. 保留原始结构：修正应在最小范围内进行，仅替换被错误识别的词语，并完整保留原始句子的结构和所有正确的词汇。

任务：
我将提供一段由ASR系统识别出的原始文本。请严格遵循以下步骤，不要包含任何额外的解释或开场白。

输入文本：{text}

操作流程：
1. 生成三个修正备选句：
   - 基于上述核心原则，识别出原始文本中的可疑错误词语
   - 生成三个仅在错误词语修正上有所不同的候选句子
   - 如果只有一个明显的正确答案，可以围绕该答案提供微小但合理的变体（例如，标点符号或个别语气词的差异），或者重复最佳答案
   - 关键：这三个句子必须保持与原文一致的句子结构

2. 选择最佳句子：
   - 从你生成的三个备选句中，选出最符合逻辑、最能还原说话者原始意图的一句
   - 以"最佳选择："作为固定开头，直接给出该句子

具体要求：
1. 识别并修正同音字错误（保持韵母一致）
2. 修正因口音或语速导致的识别错误
3. 添加合适的标点符号（。，！？、等）
4. 修正大小写（英文）和语种混用问题
5. 规范数字、日期、时间的表达方式
6. 保持原始句子结构，不进行句式改写

输出格式（严格按照以下JSON格式）：
{{
  "候选1": "第一个修正方案",
  "候选2": "第二个修正方案",
  "候选3": "第三个修正方案",
  "最佳选择": "从上述三个候选中选出的最佳方案"
}}"""
        
        try:
            # 构建请求payload
            payload = {
                "model": self.model,
                "max_tokens": 4096,
                "top_p": 1,
                "top_k": 40,
                "presence_penalty": 0,
                "frequency_penalty": 0,
                "temperature": 0.6,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "context_length_exceeded_behavior": "error",
                "echo": False
            }
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 发送请求
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # 提取LLM返回的内容
                llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 尝试解析JSON格式的响应
                try:
                    # 查找JSON部分（处理可能的额外文本）
                    json_start = llm_response.find('{')
                    json_end = llm_response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = llm_response[json_start:json_end]
                        correction_result = json.loads(json_str)
                        
                        # 返回最佳选择
                        if '最佳选择' in correction_result:
                            return correction_result['最佳选择']
                        else:
                            # 如果没有"最佳选择"字段，尝试其他可能的字段名
                            for key in ['best', 'Best', '最佳', 'best_choice']:
                                if key in correction_result:
                                    return correction_result[key]
                            # 如果都没有，返回候选1
                            return correction_result.get('候选1', text)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM JSON response: {llm_response[:200]}...")
                    # 如果无法解析JSON，直接返回原文本加标点
                    if text and not text.endswith(('。', '！', '？', '.', '!', '?')):
                        return text + '。'
                    return text
            else:
                logger.error(f"LLM API error: {response.status_code}")
                # API调用失败，返回原文本
                if text and not text.endswith(('。', '！', '？', '.', '!', '?')):
                    return text + '。'
                return text
                
        except requests.exceptions.Timeout:
            logger.error("LLM API timeout")
            # 超时处理，返回原文本
            if text and not text.endswith(('。', '！', '？', '.', '!', '?')):
                return text + '。'
            return text
        except Exception as e:
            logger.error(f"LLM processing error: {str(e)}")
            # 其他异常，返回原文本
            if text and not text.endswith(('。', '！', '？', '.', '!', '?')):
                return text + '。'
            return text

class StreamingASRServer:
    """流式ASR服务器"""
    def __init__(self):
        self.clients = {}
        self.max_segment_duration = 3.0  # 3秒
        self.lookback_duration = 9.0     # 9秒
        
    async def handle_client(self, websocket):
        """处理客户端连接"""
        client_id = id(websocket)
        logger.info(f"Client {client_id} connected from {websocket.remote_address}")
        
        # 初始化客户端状态
        self.clients[client_id] = {
            'websocket': websocket,
            'audio_buffer': AudioBuffer(),
            'vad_processor': TenVADProcessor(),
            'whisper_client': None,
            'llm_processor': None,
            'previous_results': [],
            'recent_chunks': [],
            'api_key': None,
            'enable_llm': False,
            'last_process_time': time.time(),
            'is_recording': False,
            'speech_start_index': None,  # 记录语音开始在缓冲区中的位置
            'last_chunk_end_index': 0,    # 记录上一个chunk结束的位置
            'recording_buffer': [],       # 记录整个录音过程的音频
            'recording_start_time': None  # 记录开始时间
        }
        
        try:
            # 设置WebSocket选项
            websocket.ping_interval = 20  # 每20秒发送一次ping
            websocket.ping_timeout = 10   # 10秒内没有响应则断开
            
            async for message in websocket:
                await self.process_message(client_id, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected normally")
        except Exception as e:
            logger.error(f"Client {client_id} error: {str(e)}")
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
            
    async def process_message(self, client_id, message):
        """处理客户端消息"""
        try:
            client = self.clients[client_id]
            data = json.loads(message)
            
            if data['type'] == 'config':
                # 配置消息
                await self.handle_config(client_id, data['data'])
                
            elif data['type'] == 'audio':
                # 音频数据
                await self.handle_audio(client_id, data['data'])
                
            elif data['type'] == 'control':
                # 控制命令
                await self.handle_control(client_id, data['data'])
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send_error(client_id, str(e))
            
    async def handle_config(self, client_id, config_data):
        """处理配置消息"""
        client = self.clients[client_id]
        
        if 'apiKey' in config_data:
            client['api_key'] = config_data['apiKey']
            client['whisper_client'] = WhisperClient(config_data['apiKey'])
            client['llm_processor'] = LLMProcessor(config_data['apiKey'])
            
            # 首先测试网络连通性
            logger.info("Testing network connectivity...")
            network_results = await client['whisper_client'].test_network_connectivity()
            
            # 发送网络测试结果
            network_status = []
            all_connected = True
            for service, connected, message in network_results:
                logger.info(f"{service}: {message}")
                network_status.append(f"{service}: {message}")
                if not connected:
                    all_connected = False
            
            if not all_connected:
                await self.send_error(client_id, f"网络连接测试失败\n" + "\n".join(network_status))
                # 清除client配置
                client['whisper_client'] = None
                client['api_key'] = None
                return
            
            # 网络正常，测试API连接
            logger.info("Network OK, testing API connection...")
            await self.send_status(client_id, 'testing')
            
            success, message = await client['whisper_client'].test_connection()
            
            if success:
                logger.info(f"API test successful: {message}")
                await self.send_status(client_id, 'ready')
            else:
                logger.error(f"API test failed: {message}")
                await self.send_error(client_id, f"API测试失败: {message}")
                # 清除client配置
                client['whisper_client'] = None
                client['api_key'] = None
                return
            
        if 'enableLLM' in config_data:
            client['enable_llm'] = config_data['enableLLM']
            
        # 如果只是更新enableLLM，发送就绪状态
        if 'apiKey' not in config_data and client['whisper_client']:
            await self.send_status(client_id, 'ready')
        
    async def handle_audio(self, client_id, audio_data):
        """处理音频数据"""
        client = self.clients[client_id]
        
        if not client['whisper_client']:
            await self.send_error(client_id, "API key not configured")
            return
            
        if not client['is_recording']:
            logger.warning(f"Client {client_id} sent audio but not recording")
            return
            
        # 获取音频数据
        audio_array = audio_data['audioData']
        
        # 调试信息
        if len(client['audio_buffer'].buffer) == 0:
            logger.info(f"Client {client_id} first audio chunk received, length: {len(audio_array)}")
            
        # 添加到缓冲区
        client['audio_buffer'].append(audio_array)
        
        # 如果正在录音，同时保存到recording_buffer
        if client['is_recording']:
            client['recording_buffer'].extend(audio_array)
        
        # VAD检测
        vad_result = await client['vad_processor'].process(audio_array)
        
        # 发送VAD状态（包含音量信息）
        await self.send_status(client_id, 'processing', vad_result['current_state'], 
                             rms=vad_result.get('rms', 0), 
                             max_amplitude=vad_result.get('max_amplitude', 0))
        
        # 处理VAD结果
        current_time = time.time()
        current_buffer_length = client['audio_buffer'].get_buffer_length()
        
        # 跟踪语音状态变化
        if vad_result['state_changed']:
            if vad_result['current_state'] == 'speech':
                # 记录语音开始位置 - VAD检测到的是当前chunk，所以语音开始应该是当前位置减去当前chunk的长度
                # 但为了简化，我们将语音开始位置设为当前缓冲区末尾减去一个小的回看窗口
                lookback_samples = min(len(audio_array), int(0.5 * 16000))  # 回看最多0.5秒
                client['speech_start_index'] = max(0, current_buffer_length - lookback_samples)
                client['last_chunk_end_index'] = client['speech_start_index']  # 重置chunk开始位置
                client['recent_chunks'].clear()  # 清空之前的chunks
                logger.info(f"Speech started at buffer index: {client['speech_start_index']} (current: {current_buffer_length})")
            else:  # silence
                # 语音结束
                if client['speech_start_index'] is not None:
                    # 计算语音段的长度
                    speech_length = current_buffer_length - client['speech_start_index']
                    speech_duration = speech_length / 16000
                    logger.info(f"Speech ended, duration: {speech_duration:.2f}s, start_index: {client['speech_start_index']}")
                    
                    # 检查是否需要重识别
                    if client['recent_chunks']:
                        if speech_duration <= self.lookback_duration:
                            # 语音时长小于等于9秒，重识别整个语音段
                            logger.info(f"Speech duration {speech_duration:.2f}s <= {self.lookback_duration}s, reprocessing entire speech")
                            await self.reprocess_recent_chunks(client_id)
                        else:
                            # 语音时长超过9秒，找到合适的重识别起点
                            logger.info(f"Speech duration {speech_duration:.2f}s > {self.lookback_duration}s")
                            
                            # 计算9秒前的位置（相对于当前结束位置）
                            lookback_start_index = current_buffer_length - int(self.lookback_duration * 16000)
                            # 确保不早于语音开始位置
                            if lookback_start_index < client['speech_start_index']:
                                lookback_start_index = client['speech_start_index']
                            
                            lookback_start_time = lookback_start_index / 16000
                            logger.info(f"Looking back {self.lookback_duration}s from {current_buffer_length/16000:.2f}s to {lookback_start_time:.2f}s")
                            
                            # 找到lookback_start_index右边最近的chunk边界
                            reprocess_start_index = None
                            chunks_to_reprocess = []
                            
                            for i, chunk in enumerate(client['recent_chunks']):
                                chunk_start_time = chunk['start_index'] / 16000
                                if chunk['start_index'] >= lookback_start_index:
                                    # 找到了第一个在9秒范围内的chunk
                                    reprocess_start_index = chunk['start_index']
                                    chunks_to_reprocess = client['recent_chunks'][i:]
                                    logger.info(f"Found chunk boundary at {chunk_start_time:.2f}s (chunk {i+1}/{len(client['recent_chunks'])})")
                                    break
                            
                            if reprocess_start_index is not None:
                                # 从找到的chunk边界开始重识别
                                reprocess_duration = (current_buffer_length - reprocess_start_index) / 16000
                                logger.info(f"Reprocessing from chunk boundary at {reprocess_start_index/16000:.2f}s to {current_buffer_length/16000:.2f}s (duration: {reprocess_duration:.2f}s)")
                                
                                # 更新recent_chunks，只保留要重处理的chunks
                                client['recent_chunks'] = chunks_to_reprocess
                                await self.reprocess_recent_chunks(client_id)
                            else:
                                # 没有chunk在9秒范围内，只处理最后的片段
                                last_chunk_end = client['recent_chunks'][-1]['end_index'] if client['recent_chunks'] else client['speech_start_index']
                                segment = client['audio_buffer'].buffer[last_chunk_end:current_buffer_length].copy()
                                
                                if len(segment) > 0:
                                    logger.info(f"Processing final segment only, length: {len(segment)/16000:.2f}s")
                                    await self.process_segment(client_id, segment, False)
                                
                                # 清理
                                client['audio_buffer'].buffer = client['audio_buffer'].buffer[current_buffer_length:]
                                client['recent_chunks'].clear()
                    else:
                        # 没有chunks，处理整个语音段
                        segment = client['audio_buffer'].buffer[client['speech_start_index']:current_buffer_length].copy()
                        
                        if len(segment) > 0:
                            logger.info(f"Processing speech segment (no chunks), length: {len(segment)/16000:.2f}s")
                            await self.process_segment(client_id, segment, False)
                        
                        # 清理已处理的音频
                        client['audio_buffer'].buffer = client['audio_buffer'].buffer[current_buffer_length:]
                    
                    client['speech_start_index'] = None
                    client['last_chunk_end_index'] = 0
                    client['recent_chunks'].clear()
                    
        # 检查超时 - 只在说话状态下才处理
        if vad_result['is_speaking'] and client['speech_start_index'] is not None:
            # 计算从最后一个chunk结束位置到现在的时长
            last_chunk_end = client['last_chunk_end_index']
            if last_chunk_end < client['speech_start_index']:
                last_chunk_end = client['speech_start_index']
            
            # 计算未处理音频的时长
            unprocessed_samples = current_buffer_length - last_chunk_end
            unprocessed_duration = unprocessed_samples / 16000
            
            if unprocessed_duration >= self.max_segment_duration:
                logger.info(f"Timeout during speech, unprocessed audio duration: {unprocessed_duration:.2f}s")
                
                # 计算要提取的chunk的起始和结束位置
                chunk_start = last_chunk_end
                    
                chunk_end = chunk_start + int(self.max_segment_duration * 16000)
                
                # 确保不超过当前缓冲区长度
                if chunk_end > current_buffer_length:
                    chunk_end = current_buffer_length
                    
                # 提取chunk
                segment = client['audio_buffer'].buffer[chunk_start:chunk_end].copy()
                chunk_duration = len(segment) / 16000
                
                logger.info(f"Extracting chunk: start={chunk_start/16000:.2f}s, end={chunk_end/16000:.2f}s, duration={chunk_duration:.2f}s, actual_samples={len(segment)}")
                
                if len(segment) > 0:
                    chunk_id = await self.process_segment(client_id, segment, True)
                    
                    # 记录chunk信息
                    client['recent_chunks'].append({
                        'id': chunk_id,
                        'audio_data': segment,
                        'start_index': chunk_start,
                        'end_index': chunk_end,
                        'timestamp': current_time
                    })
                    
                    # 更新最后chunk结束位置
                    client['last_chunk_end_index'] = chunk_end
                    
                    # 保持最多3个chunks
                    if len(client['recent_chunks']) > 3:
                        client['recent_chunks'].pop(0)
                        
        elif not vad_result['is_speaking'] and client['audio_buffer'].get_duration() >= self.max_segment_duration * 2:
            # 如果在静音状态下缓冲区太大（超过6秒），清理掉旧的音频
            logger.info(f"Clearing old silence audio, duration: {client['audio_buffer'].get_duration():.2f}s")
            # 保留最近3秒的音频
            keep_samples = int(self.max_segment_duration * 16000)
            if len(client['audio_buffer'].buffer) > keep_samples:
                client['audio_buffer'].buffer = client['audio_buffer'].buffer[-keep_samples:]
                # 更新索引
                removed_samples = current_buffer_length - keep_samples
                if client['speech_start_index'] is not None:
                    client['speech_start_index'] -= removed_samples
                    if client['speech_start_index'] < 0:
                        client['speech_start_index'] = 0
                
    async def process_segment(self, client_id, audio_segment, is_timeout_chunk):
        """处理音频片段"""
        client = self.clients[client_id]
        start_time = time.time()
        
        # 记录音频片段信息
        segment_duration = len(audio_segment) / 16000
        logger.info(f"Processing segment: duration={segment_duration:.2f}s, samples={len(audio_segment)}, is_timeout={is_timeout_chunk}")
        
        # 准备prompt
        prompt = ' '.join(client['previous_results'][-2:])
        
        # 调用Whisper
        asr_result = await client['whisper_client'].transcribe(audio_segment, prompt)
        
        # LLM修正（如果启用）
        llm_result = None
        if client['enable_llm'] and asr_result:
            llm_result = await client['llm_processor'].correct(asr_result)
            
        # 更新历史
        if asr_result:
            client['previous_results'].append(asr_result)
            
        # 生成segment ID
        segment_id = int(time.time() * 1000)
        
        # 计算处理时间
        processing_time = int((time.time() - start_time) * 1000)
        
        # 发送结果
        await self.send_result(client_id, {
            'segmentId': segment_id,
            'asrResult': asr_result,
            'llmResult': llm_result,
            'isTimeoutChunk': is_timeout_chunk,
            'isFinal': not is_timeout_chunk,
            'processingTime': processing_time
        })
        
        return segment_id
        
    async def reprocess_recent_chunks(self, client_id):
        """重新处理最近的chunks"""
        client = self.clients[client_id]
        start_time = time.time()
        
        # 合并音频
        combined_audio = []
        
        # 如果有recent chunks，从第一个chunk的开始位置开始
        if client['recent_chunks']:
            start_index = client['recent_chunks'][0]['start_index']
        else:
            start_index = client['speech_start_index'] or 0
            
        # 获取从开始位置到当前的所有音频
        current_buffer_length = client['audio_buffer'].get_buffer_length()
        combined_audio = client['audio_buffer'].buffer[start_index:current_buffer_length].copy()
        
        logger.info(f"Reprocessing audio from index {start_index} to {current_buffer_length}, duration: {len(combined_audio)/16000:.2f}s")
        
        # 获取要替换的segment IDs
        segment_ids_to_replace = [chunk['id'] for chunk in client['recent_chunks']]
        
        # 准备prompt - 使用chunks之前的结果（不包括将要被替换的部分）
        num_chunks_to_replace = len(client['recent_chunks'])
        if num_chunks_to_replace > 0:
            # 使用chunks之前的最后2个结果作为prompt
            prompt_results = client['previous_results'][:-num_chunks_to_replace][-2:]
        else:
            # 没有chunks，使用最后2个结果
            prompt_results = client['previous_results'][-2:]
        prompt = ' '.join(prompt_results)
        
        logger.info(f"Reprocessing with prompt from {len(prompt_results)} previous results")
        
        # 重新识别
        asr_result = await client['whisper_client'].transcribe(combined_audio, prompt)
        
        # LLM修正
        llm_result = None
        if client['enable_llm'] and asr_result:
            llm_result = await client['llm_processor'].correct(asr_result)
            
        # 计算处理时间
        processing_time = int((time.time() - start_time) * 1000)
        
        # 发送重识别结果
        await self.send_result(client_id, {
            'segmentId': int(time.time() * 1000),
            'asrResult': asr_result,
            'llmResult': llm_result,
            'isReprocessed': True,
            'replacesSegments': segment_ids_to_replace,
            'isFinal': True,
            'processingTime': processing_time
        })
        
        # 清空recent chunks
        client['recent_chunks'].clear()
        
        # 清理已处理的音频
        client['audio_buffer'].buffer = client['audio_buffer'].buffer[current_buffer_length:]
        client['speech_start_index'] = None
        client['last_chunk_end_index'] = 0
        
        # 更新历史记录
        if asr_result:
            # 移除被替换的结果
            for _ in range(len(segment_ids_to_replace)):
                if client['previous_results']:
                    client['previous_results'].pop()
            # 添加新结果
            client['previous_results'].append(asr_result)
            
    async def handle_control(self, client_id, control_data):
        """处理控制命令"""
        command = control_data.get('command')
        client = self.clients[client_id]
        
        if command == 'start':
            # 开始识别
            logger.info(f"Client {client_id} started recording")
            client['is_recording'] = True
            client['recording_buffer'] = []  # 清空录音缓冲区
            client['recording_start_time'] = datetime.now()
            await self.send_status(client_id, 'ready')
            
        elif command == 'stop':
            # 停止识别
            logger.info(f"Client {client_id} stopped recording")
            client['is_recording'] = False
            
            # 保存整个录音文件
            if client['recording_buffer'] and client['recording_start_time']:
                try:
                    # 创建log/wavs目录
                    wavs_dir = os.path.join(os.path.dirname(__file__), 'log', 'wavs')
                    os.makedirs(wavs_dir, exist_ok=True)
                    
                    # 生成文件名
                    timestamp = client['recording_start_time'].strftime('%Y%m%d_%H%M%S_%f')[:-3]
                    wav_filename = f"{timestamp}.wav"
                    wav_path = os.path.join(wavs_dir, wav_filename)
                    
                    # 保存音频文件
                    with wave.open(wav_path, 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(16000)
                        
                        # 转换为numpy数组
                        audio_np = np.array(client['recording_buffer'], dtype=np.float32)
                        audio_np = np.clip(audio_np, -1.0, 1.0)
                        audio_int16 = (audio_np * 32767).astype(np.int16)
                        wav_file.writeframes(audio_int16.tobytes())
                    
                    duration = len(client['recording_buffer']) / 16000
                    logger.info(f"Saved complete recording: {wav_filename}, duration: {duration:.2f}s")
                    
                except Exception as e:
                    logger.error(f"Failed to save recording: {str(e)}")
            
            # 清理状态
            client['audio_buffer'].clear()
            client['recent_chunks'].clear()
            client['recording_buffer'] = []
            client['recording_start_time'] = None
            await self.send_status(client_id, 'ready')
            
        elif command == 'reset':
            # 重置状态
            logger.info(f"Client {client_id} reset session")
            client['is_recording'] = False
            client['audio_buffer'].clear()
            client['recent_chunks'].clear()
            client['previous_results'].clear()
            client['recording_buffer'] = []
            client['recording_start_time'] = None
            await self.send_status(client_id, 'ready')
            
    async def send_message(self, client_id, message):
        """发送消息给客户端"""
        client = self.clients.get(client_id)
        if client and client['websocket']:
            try:
                await client['websocket'].send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message: {str(e)}")
                
    async def send_result(self, client_id, result_data):
        """发送识别结果"""
        message = {
            'type': 'result',
            'data': result_data,
            'timestamp': int(time.time() * 1000)
        }
        await self.send_message(client_id, message)
        
    async def send_status(self, client_id, status, vad_state=None, **kwargs):
        """发送状态消息"""
        data = {'status': status}
        if vad_state:
            data['vadState'] = vad_state
        # 添加额外的状态信息（如音量）
        data.update(kwargs)
            
        message = {
            'type': 'status',
            'data': data,
            'timestamp': int(time.time() * 1000)
        }
        await self.send_message(client_id, message)
        
    async def send_error(self, client_id, error_message):
        """发送错误消息"""
        message = {
            'type': 'error',
            'data': {
                'error': error_message,
                'code': 'ERROR'
            },
            'timestamp': int(time.time() * 1000)
        }
        await self.send_message(client_id, message)

async def main():
    """启动服务器"""
    # 显示代理设置
    http_proxy = os.environ.get('http_proxy', 'Not set')
    https_proxy = os.environ.get('https_proxy', 'Not set')
    logger.info(f"Proxy settings - HTTP: {http_proxy}, HTTPS: {https_proxy}")
    
    server = StreamingASRServer()
    
    # 启动WebSocket服务器
    async with websockets.serve(server.handle_client, "localhost", 8765):
        logger.info("VAD-Based Streaming ASR Server started on ws://localhost:8765")
        await asyncio.Future()  # 保持运行

if __name__ == "__main__":
    asyncio.run(main())