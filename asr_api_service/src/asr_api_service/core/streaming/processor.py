"""Streaming audio processor with VAD and ASR integration."""

import asyncio
import time
from typing import Dict, List, Optional, Any

from fastapi import WebSocket
import structlog

from asr_api_service.config import settings
from asr_api_service.core.audio.buffer import AudioBuffer
from asr_api_service.core.audio.vad import VADProcessor, VADResult
from asr_api_service.core.asr.whisper import WhisperASRProvider
from asr_api_service.exceptions import StreamingError, ASRServiceError
from asr_api_service.models.streaming import (
    StreamingConfig,
    StreamingAudioData,
    StreamingControl,
    StreamingResult,
    StreamingMessage,
    VADStatus,
)

logger = structlog.get_logger(__name__)


class AudioSegment:
    """Represents a segment of audio for processing."""
    
    def __init__(self, audio_data: List[float], start_index: int, end_index: int):
        self.audio_data = audio_data
        self.start_index = start_index
        self.end_index = end_index
        self.timestamp = time.time()
        self.segment_id = int(self.timestamp * 1000)


class StreamingProcessor:
    """Processes streaming audio with VAD and ASR."""
    
    def __init__(self, client_id: str, config: StreamingConfig, websocket: WebSocket):
        self.client_id = client_id
        self.config = config
        self.websocket = websocket
        
        # Audio processing components
        self.audio_buffer = AudioBuffer(sample_rate=settings.audio_sample_rate)
        self.vad_processor: Optional[VADProcessor] = None
        self.asr_provider: Optional[WhisperASRProvider] = None
        
        # Processing state
        self.is_recording = False
        self.speech_start_index: Optional[int] = None
        self.last_chunk_end_index = 0
        self.recent_chunks: List[AudioSegment] = []
        self.previous_results: List[str] = []
        
        # Configuration
        self.max_segment_duration = config.chunk_duration or settings.audio_chunk_duration
        self.lookback_duration = settings.audio_lookback_duration
        
    async def initialize(self) -> None:
        """Initialize the streaming processor."""
        try:
            # Initialize VAD processor
            vad_threshold = self.config.vad_threshold or settings.vad_threshold
            self.vad_processor = VADProcessor(
                threshold=vad_threshold,
                silence_duration=settings.vad_silence_duration,
                hop_size=settings.vad_hop_size,
            )
            
            # Initialize ASR provider
            if not self.config.api_key:
                raise StreamingError("API key is required", self.client_id)
            
            self.asr_provider = WhisperASRProvider(
                api_key=self.config.api_key,
                api_url=settings.get_asr_api_url(),
                model=settings.get_asr_model(),
                timeout=30.0,
            )
            
            # Test ASR connection
            success, message = await self.asr_provider.test_connection()
            if not success:
                raise StreamingError(f"ASR provider test failed: {message}", self.client_id)
            
            logger.info(
                "Streaming processor initialized",
                client_id=self.client_id,
                vad_threshold=vad_threshold,
                chunk_duration=self.max_segment_duration,
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize streaming processor",
                client_id=self.client_id,
                error=str(e),
            )
            raise StreamingError(f"Initialization failed: {str(e)}", self.client_id)
    
    async def process_audio(self, audio_data: StreamingAudioData) -> Optional[int]:
        """Process incoming audio data.
        
        Args:
            audio_data: Streaming audio data
            
        Returns:
            Processing time in milliseconds if transcription occurred
        """
        if not self.vad_processor or not self.asr_provider:
            raise StreamingError("Processor not initialized", self.client_id)
        
        if not self.is_recording:
            logger.debug("Received audio but not recording", client_id=self.client_id)
            return None
        
        start_time = time.time()
        
        try:
            # Add audio to buffer
            self.audio_buffer.append(audio_data.audio_data)
            
            # Process with VAD
            vad_result = await self.vad_processor.process(audio_data.audio_data)
            
            # Send VAD status
            await self._send_vad_status(vad_result)
            
            # Handle VAD state changes
            processing_time = await self._handle_vad_result(vad_result)
            
            return processing_time
            
        except Exception as e:
            logger.error(
                "Audio processing error",
                client_id=self.client_id,
                error=str(e),
            )
            raise StreamingError(f"Audio processing failed: {str(e)}", self.client_id)
    
    async def _handle_vad_result(self, vad_result: VADResult) -> Optional[int]:
        """Handle VAD processing result.
        
        Args:
            vad_result: VAD processing result
            
        Returns:
            Processing time in milliseconds if transcription occurred
        """
        current_buffer_length = self.audio_buffer.get_buffer_length()
        
        # Handle state changes
        if vad_result.state_changed:
            if vad_result.current_state == 'speech':
                # Speech started - mark the beginning
                lookback_samples = min(len(self.audio_buffer.buffer), int(0.5 * settings.audio_sample_rate))
                self.speech_start_index = max(0, current_buffer_length - lookback_samples)
                self.last_chunk_end_index = self.speech_start_index
                self.recent_chunks.clear()
                
                logger.debug(
                    "Speech started",
                    client_id=self.client_id,
                    start_index=self.speech_start_index,
                )
                
            else:  # silence
                # Speech ended - process the complete segment
                if self.speech_start_index is not None:
                    processing_time = await self._process_speech_end(current_buffer_length)
                    self._reset_speech_state()
                    return processing_time
        
        # Check for timeout during speech
        if (vad_result.is_speaking and 
            self.speech_start_index is not None and
            self._should_process_timeout_chunk(current_buffer_length)):
            
            return await self._process_timeout_chunk(current_buffer_length)
        
        # Clean up old audio if silent for too long
        if not vad_result.is_speaking and self.audio_buffer.get_duration() > self.max_segment_duration * 2:
            self._cleanup_old_audio()
        
        return None
    
    def _should_process_timeout_chunk(self, current_buffer_length: int) -> bool:
        """Check if we should process a timeout chunk."""
        unprocessed_samples = current_buffer_length - self.last_chunk_end_index
        unprocessed_duration = unprocessed_samples / settings.audio_sample_rate
        return unprocessed_duration >= self.max_segment_duration
    
    async def _process_timeout_chunk(self, current_buffer_length: int) -> int:
        """Process a timeout chunk during ongoing speech."""
        chunk_start = self.last_chunk_end_index
        chunk_end = chunk_start + int(self.max_segment_duration * settings.audio_sample_rate)
        chunk_end = min(chunk_end, current_buffer_length)
        
        # Extract chunk
        segment_audio = self.audio_buffer.extract_segment(
            start_index=chunk_start,
            duration=None if chunk_end == current_buffer_length else (chunk_end - chunk_start) / settings.audio_sample_rate
        )
        
        if not segment_audio:
            return 0
        
        # Create segment
        segment = AudioSegment(segment_audio, chunk_start, chunk_end)
        
        # Process segment
        processing_time = await self._process_segment(segment, is_timeout_chunk=True)
        
        # Update state
        self.recent_chunks.append(segment)
        self.last_chunk_end_index = chunk_end
        
        # Keep only recent chunks
        if len(self.recent_chunks) > 3:
            self.recent_chunks.pop(0)
        
        return processing_time
    
    async def _process_speech_end(self, current_buffer_length: int) -> int:
        """Process the end of a speech segment."""
        if self.speech_start_index is None:
            return 0
        
        speech_length = current_buffer_length - self.speech_start_index
        speech_duration = speech_length / settings.audio_sample_rate
        
        logger.debug(
            "Speech ended",
            client_id=self.client_id,
            duration=speech_duration,
            chunks_count=len(self.recent_chunks),
        )
        
        # Decide whether to reprocess or just process the final segment
        if self.recent_chunks and speech_duration <= self.lookback_duration:
            # Reprocess entire speech segment
            return await self._reprocess_speech_segment(current_buffer_length)
        elif self.recent_chunks:
            # Long speech - reprocess from lookback point
            return await self._reprocess_with_lookback(current_buffer_length)
        else:
            # No chunks - process entire segment
            return await self._process_final_segment(current_buffer_length)
    
    async def _reprocess_speech_segment(self, current_buffer_length: int) -> int:
        """Reprocess the entire speech segment."""
        start_index = self.speech_start_index or 0
        
        # Extract entire speech segment
        segment_audio = self.audio_buffer.extract_segment(
            start_index=start_index,
            duration=None
        )
        
        if not segment_audio:
            return 0
        
        # Create segment
        segment = AudioSegment(segment_audio, start_index, current_buffer_length)
        
        # Get segments to replace
        replaced_segment_ids = [chunk.segment_id for chunk in self.recent_chunks]
        
        # Process with reprocessing context
        return await self._process_segment(
            segment,
            is_timeout_chunk=False,
            is_reprocessed=True,
            replaces_segments=replaced_segment_ids
        )
    
    async def _reprocess_with_lookback(self, current_buffer_length: int) -> int:
        """Reprocess from lookback point for long speech segments."""
        lookback_start_index = current_buffer_length - int(self.lookback_duration * settings.audio_sample_rate)
        lookback_start_index = max(lookback_start_index, self.speech_start_index or 0)
        
        # Find chunk boundary near lookback point
        reprocess_start_index = lookback_start_index
        chunks_to_replace = []
        
        for chunk in self.recent_chunks:
            if chunk.start_index >= lookback_start_index:
                reprocess_start_index = chunk.start_index
                chunks_to_replace = [c for c in self.recent_chunks if c.start_index >= reprocess_start_index]
                break
        
        # Extract segment from reprocess point
        segment_audio = self.audio_buffer.extract_segment(
            start_index=reprocess_start_index,
            duration=None
        )
        
        if not segment_audio:
            return 0
        
        # Create segment
        segment = AudioSegment(segment_audio, reprocess_start_index, current_buffer_length)
        
        # Get segments to replace
        replaced_segment_ids = [chunk.segment_id for chunk in chunks_to_replace]
        
        # Process with reprocessing context
        return await self._process_segment(
            segment,
            is_timeout_chunk=False,
            is_reprocessed=True,
            replaces_segments=replaced_segment_ids
        )
    
    async def _process_final_segment(self, current_buffer_length: int) -> int:
        """Process final segment when no chunks exist."""
        start_index = self.speech_start_index or 0
        
        segment_audio = self.audio_buffer.extract_segment(
            start_index=start_index,
            duration=None
        )
        
        if not segment_audio:
            return 0
        
        segment = AudioSegment(segment_audio, start_index, current_buffer_length)
        return await self._process_segment(segment, is_timeout_chunk=False)
    
    async def _process_segment(
        self,
        segment: AudioSegment,
        is_timeout_chunk: bool = False,
        is_reprocessed: bool = False,
        replaces_segments: Optional[List[int]] = None
    ) -> int:
        """Process an audio segment with ASR.
        
        Args:
            segment: Audio segment to process
            is_timeout_chunk: Whether this is a timeout chunk
            is_reprocessed: Whether this replaces previous segments
            replaces_segments: List of segment IDs this replaces
            
        Returns:
            Processing time in milliseconds
        """
        start_time = time.time()
        
        try:
            # Prepare context prompt
            prompt = ' '.join(self.previous_results[-2:]) if self.previous_results else ""
            
            # Transcribe audio
            asr_result = await self.asr_provider.transcribe(
                audio_data=segment.audio_data,
                sample_rate=settings.audio_sample_rate,
                prompt=prompt,
                language=self.config.language,
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # TODO: Add LLM correction if enabled
            corrected_text = None
            if self.config.enable_llm and asr_result.text:
                # Placeholder for LLM correction
                pass
            
            # Update history for non-timeout chunks or final results
            if not is_timeout_chunk or not self.recent_chunks:
                if is_reprocessed and replaces_segments:
                    # Remove replaced results
                    for _ in range(len(replaces_segments)):
                        if self.previous_results:
                            self.previous_results.pop()
                
                if asr_result.text:
                    self.previous_results.append(asr_result.text)
                    # Keep limited history
                    if len(self.previous_results) > 10:
                        self.previous_results.pop(0)
            
            # Create and send result
            result = StreamingResult(
                segment_id=segment.segment_id,
                text=asr_result.text,
                corrected_text=corrected_text,
                is_final=not is_timeout_chunk,
                is_timeout_chunk=is_timeout_chunk,
                is_reprocessed=is_reprocessed,
                replaces_segments=replaces_segments or [],
                processing_time_ms=processing_time_ms,
                metadata={
                    "audio_duration": len(segment.audio_data) / settings.audio_sample_rate,
                    "start_index": segment.start_index,
                    "end_index": segment.end_index,
                },
            )
            
            await self._send_result(result)
            
            logger.debug(
                "Segment processed",
                client_id=self.client_id,
                segment_id=segment.segment_id,
                text_length=len(asr_result.text),
                processing_time_ms=processing_time_ms,
                is_timeout_chunk=is_timeout_chunk,
                is_reprocessed=is_reprocessed,
            )
            
            return processing_time_ms
            
        except ASRServiceError as e:
            logger.error(
                "ASR processing error",
                client_id=self.client_id,
                segment_id=segment.segment_id,
                error=e.message,
            )
            # Send empty result to maintain flow
            await self._send_result(StreamingResult(
                segment_id=segment.segment_id,
                text="",
                is_final=not is_timeout_chunk,
                processing_time_ms=int((time.time() - start_time) * 1000),
                metadata={"error": "ASR processing failed"},
            ))
            return int((time.time() - start_time) * 1000)
    
    async def handle_control(self, control_data: Any) -> None:
        """Handle control commands.
        
        Args:
            control_data: Control command data
        """
        if isinstance(control_data, dict):
            control = StreamingControl(**control_data)
        else:
            control = control_data
        
        command = control.command
        
        logger.debug(
            "Handling control command",
            client_id=self.client_id,
            command=command,
        )
        
        if command == "start":
            self.is_recording = True
            self._reset_speech_state()
            logger.info("Recording started", client_id=self.client_id)
            
        elif command == "stop":
            self.is_recording = False
            # Process any remaining audio
            if self.speech_start_index is not None:
                current_buffer_length = self.audio_buffer.get_buffer_length()
                await self._process_speech_end(current_buffer_length)
            self._reset_speech_state()
            logger.info("Recording stopped", client_id=self.client_id)
            
        elif command == "reset":
            self.is_recording = False
            self._reset_speech_state()
            self.audio_buffer.clear()
            self.previous_results.clear()
            if self.vad_processor:
                self.vad_processor.reset()
            logger.info("Session reset", client_id=self.client_id)
            
        elif command == "pause":
            self.is_recording = False
            logger.info("Recording paused", client_id=self.client_id)
            
        elif command == "resume":
            self.is_recording = True
            logger.info("Recording resumed", client_id=self.client_id)
    
    def _reset_speech_state(self) -> None:
        """Reset speech processing state."""
        self.speech_start_index = None
        self.last_chunk_end_index = 0
        self.recent_chunks.clear()
    
    def _cleanup_old_audio(self) -> None:
        """Clean up old audio data."""
        keep_duration = self.max_segment_duration
        self.audio_buffer.trim_old_data(keep_duration)
    
    async def _send_vad_status(self, vad_result: VADResult) -> None:
        """Send VAD status to client."""
        vad_status = VADStatus(
            is_speaking=vad_result.is_speaking,
            current_state=vad_result.current_state,
            state_changed=vad_result.state_changed,
            probability=vad_result.probability,
            rms=vad_result.rms,
            max_amplitude=vad_result.max_amplitude,
            silence_timeout=vad_result.silence_timeout,
        )
        
        status_message = StreamingMessage.create_status(
            StreamingStatus(
                status="processing",
                vad_state=vad_status,
                client_id=self.client_id,
            )
        )
        
        await self.websocket.send_text(status_message.model_dump_json())
    
    async def _send_result(self, result: StreamingResult) -> None:
        """Send transcription result to client."""
        result_message = StreamingMessage.create_result(result)
        await self.websocket.send_text(result_message.model_dump_json())
    
    async def cleanup(self) -> None:
        """Clean up processor resources."""
        logger.info("Cleaning up streaming processor", client_id=self.client_id)
        
        # Reset state
        self.is_recording = False
        self._reset_speech_state()
        
        # Clear buffers
        self.audio_buffer.clear()
        self.previous_results.clear()
        
        # Reset VAD if available
        if self.vad_processor:
            self.vad_processor.reset()