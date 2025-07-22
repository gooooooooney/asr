"""Audio buffer management."""

import time
from typing import List, Optional

import numpy as np

from asr_api_service.exceptions import AudioProcessingError


class AudioBuffer:
    """Audio buffer for managing streaming audio data."""

    def __init__(self, sample_rate: int = 16000):
        """Initialize audio buffer.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.buffer: List[float] = []
        self.start_time = time.time()
        self.last_access_time = time.time()
        
    def append(self, audio_data: List[float]) -> None:
        """Add audio data to the buffer.
        
        Args:
            audio_data: Audio samples to append
            
        Raises:
            AudioProcessingError: If audio data is invalid
        """
        if not audio_data:
            return
            
        if not isinstance(audio_data, (list, np.ndarray)):
            raise AudioProcessingError(
                "Audio data must be a list or numpy array",
                audio_info={"type": type(audio_data).__name__}
            )
            
        # Convert to list if numpy array
        if isinstance(audio_data, np.ndarray):
            audio_data = audio_data.tolist()
            
        # Validate audio data range
        if any(not isinstance(sample, (int, float)) for sample in audio_data):
            raise AudioProcessingError("All audio samples must be numeric")
            
        # Clip audio data to valid range
        clipped_data = [max(-1.0, min(1.0, float(sample))) for sample in audio_data]
        
        self.buffer.extend(clipped_data)
        self.last_access_time = time.time()
        
    def get_duration(self) -> float:
        """Get the duration of audio data in the buffer.
        
        Returns:
            Duration in seconds
        """
        return len(self.buffer) / self.sample_rate
        
    def get_buffer_length(self) -> int:
        """Get the number of samples in the buffer.
        
        Returns:
            Number of samples
        """
        return len(self.buffer)
        
    def extract_segment(
        self, 
        duration: Optional[float] = None, 
        start_index: int = 0,
        remove_extracted: bool = False
    ) -> List[float]:
        """Extract a segment of audio data.
        
        Args:
            duration: Duration in seconds to extract (None for all remaining)
            start_index: Starting sample index
            remove_extracted: Whether to remove extracted data from buffer
            
        Returns:
            Extracted audio samples
            
        Raises:
            AudioProcessingError: If indices are invalid
        """
        if start_index < 0 or start_index > len(self.buffer):
            raise AudioProcessingError(
                f"Invalid start index: {start_index}",
                audio_info={"buffer_length": len(self.buffer)}
            )
            
        if duration is None:
            # Extract all remaining samples
            segment = self.buffer[start_index:].copy()
            if remove_extracted:
                self.buffer = self.buffer[:start_index]
        else:
            # Extract specific duration
            samples = int(duration * self.sample_rate)
            end_index = min(start_index + samples, len(self.buffer))
            segment = self.buffer[start_index:end_index].copy()
            
            if remove_extracted and start_index == 0:
                # Remove from beginning
                self.buffer = self.buffer[end_index:]
                
        self.last_access_time = time.time()
        return segment
        
    def extract_recent(self, duration: float) -> List[float]:
        """Extract recent audio data from the end of the buffer.
        
        Args:
            duration: Duration in seconds to extract
            
        Returns:
            Recent audio samples
        """
        samples = int(duration * self.sample_rate)
        start_index = max(0, len(self.buffer) - samples)
        return self.buffer[start_index:]
        
    def trim_old_data(self, max_duration: float) -> None:
        """Remove old audio data to keep buffer size manageable.
        
        Args:
            max_duration: Maximum duration to keep in buffer
        """
        max_samples = int(max_duration * self.sample_rate)
        if len(self.buffer) > max_samples:
            # Keep only the most recent samples
            self.buffer = self.buffer[-max_samples:]
            
    def clear(self) -> None:
        """Clear the audio buffer."""
        self.buffer.clear()
        self.last_access_time = time.time()
        
    def get_rms_level(self, start_index: int = 0, duration: Optional[float] = None) -> float:
        """Calculate RMS level of audio data.
        
        Args:
            start_index: Starting sample index
            duration: Duration to analyze (None for all remaining)
            
        Returns:
            RMS level (0.0 to 1.0)
        """
        if not self.buffer:
            return 0.0
            
        if duration is None:
            segment = self.buffer[start_index:]
        else:
            samples = int(duration * self.sample_rate)
            end_index = min(start_index + samples, len(self.buffer))
            segment = self.buffer[start_index:end_index]
            
        if not segment:
            return 0.0
            
        # Calculate RMS
        squares = [sample ** 2 for sample in segment]
        mean_square = sum(squares) / len(squares)
        return mean_square ** 0.5
        
    def get_peak_level(self, start_index: int = 0, duration: Optional[float] = None) -> float:
        """Get peak amplitude level of audio data.
        
        Args:
            start_index: Starting sample index
            duration: Duration to analyze (None for all remaining)
            
        Returns:
            Peak level (0.0 to 1.0)
        """
        if not self.buffer:
            return 0.0
            
        if duration is None:
            segment = self.buffer[start_index:]
        else:
            samples = int(duration * self.sample_rate)
            end_index = min(start_index + samples, len(self.buffer))
            segment = self.buffer[start_index:end_index]
            
        if not segment:
            return 0.0
            
        return max(abs(sample) for sample in segment)
        
    def to_numpy(
        self, 
        start_index: int = 0, 
        duration: Optional[float] = None,
        dtype: np.dtype = np.float32
    ) -> np.ndarray:
        """Convert buffer data to numpy array.
        
        Args:
            start_index: Starting sample index
            duration: Duration to convert (None for all remaining)
            dtype: NumPy data type
            
        Returns:
            NumPy array of audio data
        """
        if duration is None:
            segment = self.buffer[start_index:]
        else:
            samples = int(duration * self.sample_rate)
            end_index = min(start_index + samples, len(self.buffer))
            segment = self.buffer[start_index:end_index]
            
        return np.array(segment, dtype=dtype)
        
    def get_stats(self) -> dict:
        """Get buffer statistics.
        
        Returns:
            Dictionary with buffer statistics
        """
        return {
            "buffer_length": len(self.buffer),
            "duration_seconds": self.get_duration(),
            "sample_rate": self.sample_rate,
            "rms_level": self.get_rms_level(),
            "peak_level": self.get_peak_level(),
            "buffer_start_time": self.start_time,
            "last_access_time": self.last_access_time,
        }