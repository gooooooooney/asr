"""Voice Activity Detection (VAD) implementation."""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import structlog

from asr_api_service.exceptions import VADError
from asr_api_service.config import settings

logger = structlog.get_logger(__name__)


class VADResult:
    """VAD processing result."""

    def __init__(
        self,
        is_speaking: bool,
        state_changed: bool,
        current_state: str,
        probability: float,
        rms: float,
        max_amplitude: float,
        silence_timeout: bool = False,
    ):
        self.is_speaking = is_speaking
        self.state_changed = state_changed
        self.current_state = current_state  # 'speech' or 'silence'
        self.probability = probability
        self.rms = rms
        self.max_amplitude = max_amplitude
        self.silence_timeout = silence_timeout

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "is_speaking": self.is_speaking,
            "state_changed": self.state_changed,
            "current_state": self.current_state,
            "probability": self.probability,
            "rms": self.rms,
            "max_amplitude": self.max_amplitude,
            "silence_timeout": self.silence_timeout,
        }


class VADProcessor:
    """Voice Activity Detection processor with TEN-VAD integration."""

    def __init__(
        self,
        threshold: float = 0.5,
        silence_duration: float = 0.8,
        hop_size: int = 256,
    ):
        """Initialize VAD processor.
        
        Args:
            threshold: VAD threshold (0.0 to 1.0)
            silence_duration: Minimum silence duration to trigger timeout
            hop_size: VAD hop size in samples
        """
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.hop_size = hop_size
        self.is_speaking = False
        self.silence_start: Optional[float] = None
        self.debug_counter = 0
        
        # Try to initialize TEN-VAD
        self.ten_vad = None
        self.use_real_vad = False
        self.vad_buffer: List[int] = []
        
        self._initialize_ten_vad()
        
    def _initialize_ten_vad(self) -> None:
        """Initialize TEN-VAD if available."""
        try:
            # Add parent project's ten-vad path to Python path
            current_file = Path(__file__).resolve()
            ten_vad_path = current_file.parent.parent.parent.parent.parent / "ten-vad" / "include"
            
            if ten_vad_path.exists() and str(ten_vad_path) not in sys.path:
                sys.path.insert(0, str(ten_vad_path))
            
            from ten_vad import TenVad
            
            self.ten_vad = TenVad(hop_size=self.hop_size, threshold=self.threshold)
            self.use_real_vad = True
            
            logger.info(
                "TEN-VAD initialized successfully",
                hop_size=self.hop_size,
                threshold=self.threshold,
            )
            
        except ImportError as e:
            logger.warning(
                "TEN-VAD not available, falling back to simple VAD",
                error=str(e),
            )
            self.use_real_vad = False
        except Exception as e:
            logger.error(
                "Failed to initialize TEN-VAD",
                error=str(e),
                error_type=type(e).__name__,
            )
            self.use_real_vad = False

    async def process(self, audio_data: List[float]) -> VADResult:
        """Process audio data for voice activity detection.
        
        Args:
            audio_data: Audio samples to process
            
        Returns:
            VAD processing result
            
        Raises:
            VADError: If VAD processing fails
        """
        try:
            if not audio_data:
                raise VADError("Empty audio data provided")
            
            audio_array = np.array(audio_data, dtype=np.float32)
            
            # Calculate audio metrics
            rms = float(np.sqrt(np.mean(audio_array ** 2)))
            max_amplitude = float(np.max(np.abs(audio_array)))
            
            # Perform VAD
            if self.use_real_vad and self.ten_vad:
                current_speaking, probability = await self._process_with_ten_vad(audio_array)
            else:
                current_speaking, probability = self._process_with_simple_vad(audio_array, rms)
            
            # Check for state change
            state_changed = current_speaking != self.is_speaking
            current_state = 'speech' if current_speaking else 'silence'
            
            # Handle state changes
            if state_changed:
                logger.info(
                    "VAD state changed",
                    from_state='silence' if current_speaking else 'speech',
                    to_state=current_state,
                    probability=probability,
                    rms=rms,
                )
                
                if not current_speaking:
                    self.silence_start = time.time()
                else:
                    self.silence_start = None
                    
                self.is_speaking = current_speaking
            
            # Check for silence timeout
            silence_timeout = False
            if (self.silence_start and 
                not current_speaking and 
                (time.time() - self.silence_start) >= self.silence_duration):
                silence_timeout = True
            
            # Debug logging
            self.debug_counter += 1
            if self.debug_counter % 20 == 0:  # Log every 20th call
                logger.debug(
                    "VAD debug info",
                    speaking=current_speaking,
                    probability=probability,
                    rms=rms,
                    max_amplitude=max_amplitude,
                    vad_type="ten-vad" if self.use_real_vad else "simple",
                )
            
            return VADResult(
                is_speaking=current_speaking,
                state_changed=state_changed,
                current_state=current_state,
                probability=probability,
                rms=rms,
                max_amplitude=max_amplitude,
                silence_timeout=silence_timeout,
            )
            
        except Exception as e:
            logger.exception("VAD processing error", error=str(e))
            raise VADError(
                f"VAD processing failed: {str(e)}",
                vad_info={
                    "audio_length": len(audio_data) if audio_data else 0,
                    "use_real_vad": self.use_real_vad,
                    "threshold": self.threshold,
                }
            )

    async def _process_with_ten_vad(self, audio_array: np.ndarray) -> tuple[bool, float]:
        """Process audio with TEN-VAD.
        
        Args:
            audio_array: Audio data as numpy array
            
        Returns:
            Tuple of (is_speaking, probability)
        """
        # Convert to int16 for TEN-VAD
        audio_int16 = (np.clip(audio_array, -1.0, 1.0) * 32767).astype(np.int16)
        
        # Add to VAD buffer
        self.vad_buffer.extend(audio_int16.tolist())
        
        probability = 0.0
        voice_flag = 0
        
        # Process complete frames
        while len(self.vad_buffer) >= self.hop_size:
            frame = np.array(self.vad_buffer[:self.hop_size], dtype=np.int16)
            self.vad_buffer = self.vad_buffer[self.hop_size:]
            
            try:
                probability, voice_flag = self.ten_vad.process(frame)
            except Exception as e:
                logger.warning("TEN-VAD process error, using fallback", error=str(e))
                # Fallback to simple VAD
                rms = float(np.sqrt(np.mean((frame.astype(np.float32) / 32767) ** 2)))
                voice_flag = 1 if rms > 0.01 else 0
                probability = rms
        
        return voice_flag == 1, float(probability)

    def _process_with_simple_vad(self, audio_array: np.ndarray, rms: float) -> tuple[bool, float]:
        """Process audio with simple energy-based VAD.
        
        Args:
            audio_array: Audio data as numpy array
            rms: RMS energy level
            
        Returns:
            Tuple of (is_speaking, probability)
        """
        # Simple threshold-based VAD
        is_speaking = rms > self.threshold
        return is_speaking, rms

    def reset(self) -> None:
        """Reset VAD processor state."""
        self.is_speaking = False
        self.silence_start = None
        self.vad_buffer.clear()
        self.debug_counter = 0
        
        logger.info("VAD processor reset")

    def get_stats(self) -> Dict[str, Any]:
        """Get VAD processor statistics.
        
        Returns:
            Dictionary with VAD statistics
        """
        return {
            "threshold": self.threshold,
            "silence_duration": self.silence_duration,
            "hop_size": self.hop_size,
            "is_speaking": self.is_speaking,
            "use_real_vad": self.use_real_vad,
            "vad_buffer_size": len(self.vad_buffer),
            "silence_start": self.silence_start,
        }