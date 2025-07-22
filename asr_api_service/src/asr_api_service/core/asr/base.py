"""Base ASR provider interface."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

import numpy as np


class ASRResult:
    """ASR transcription result."""

    def __init__(
        self,
        text: str,
        confidence: Optional[float] = None,
        processing_time_ms: Optional[int] = None,
        segments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.text = text
        self.confidence = confidence
        self.processing_time_ms = processing_time_ms
        self.segments = segments or []
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "segments": self.segments,
            "metadata": self.metadata,
        }


class ASRProvider(ABC):
    """Abstract base class for ASR providers."""

    def __init__(self, api_key: str, api_url: str, model: str):
        """Initialize ASR provider.
        
        Args:
            api_key: API key for the ASR service
            api_url: API endpoint URL
            model: Model name to use
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    @abstractmethod
    async def transcribe(
        self,
        audio_data: List[float],
        sample_rate: int = 16000,
        prompt: str = "",
        language: Optional[str] = None,
        **kwargs
    ) -> ASRResult:
        """Transcribe audio data.
        
        Args:
            audio_data: Audio samples
            sample_rate: Audio sample rate
            prompt: Context prompt for better recognition
            language: Target language code
            **kwargs: Additional provider-specific options
            
        Returns:
            ASR transcription result
        """
        pass

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test connection to the ASR service.
        
        Returns:
            Tuple of (success, message)
        """
        pass

    def create_audio_array(
        self, 
        audio_data: List[float], 
        sample_rate: int = 16000,
        target_dtype: np.dtype = np.int16
    ) -> np.ndarray:
        """Convert audio data to numpy array with specified format.
        
        Args:
            audio_data: Audio samples
            sample_rate: Audio sample rate
            target_dtype: Target numpy data type
            
        Returns:
            NumPy array of audio data
        """
        audio_array = np.array(audio_data, dtype=np.float32)
        
        # Clip to valid range
        audio_array = np.clip(audio_array, -1.0, 1.0)
        
        # Convert to target dtype
        if target_dtype == np.int16:
            audio_array = (audio_array * 32767).astype(np.int16)
        elif target_dtype == np.int32:
            audio_array = (audio_array * 2147483647).astype(np.int32)
        # Keep as float32 if target_dtype is float32
        
        return audio_array

    def validate_audio_data(self, audio_data: List[float], min_duration: float = 0.1) -> None:
        """Validate audio data.
        
        Args:
            audio_data: Audio samples to validate
            min_duration: Minimum required duration in seconds
            
        Raises:
            ValueError: If audio data is invalid
        """
        if not audio_data:
            raise ValueError("Audio data is empty")
        
        if not isinstance(audio_data, (list, np.ndarray)):
            raise ValueError("Audio data must be a list or numpy array")
        
        duration = len(audio_data) / 16000  # Assume 16kHz
        if duration < min_duration:
            raise ValueError(f"Audio duration {duration:.2f}s is less than minimum {min_duration}s")
        
        # Check for all zeros (silence)
        if all(abs(sample) < 1e-6 for sample in audio_data):
            raise ValueError("Audio data appears to be silent")

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return self.__class__.__name__.replace("ASRProvider", "").lower()