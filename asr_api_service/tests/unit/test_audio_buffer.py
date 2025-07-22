"""Unit tests for AudioBuffer."""

import pytest
import numpy as np

from asr_api_service.core.audio.buffer import AudioBuffer
from asr_api_service.exceptions import AudioProcessingError


class TestAudioBuffer:
    """Test cases for AudioBuffer class."""
    
    def test_init(self):
        """Test AudioBuffer initialization."""
        buffer = AudioBuffer(sample_rate=16000)
        assert buffer.sample_rate == 16000
        assert len(buffer.buffer) == 0
        assert buffer.get_duration() == 0.0
        assert buffer.get_buffer_length() == 0
    
    def test_append_audio_data(self):
        """Test appending audio data."""
        buffer = AudioBuffer()
        audio_data = [0.1, 0.2, -0.1, -0.2]
        
        buffer.append(audio_data)
        assert len(buffer.buffer) == 4
        assert buffer.get_duration() == 4.0 / 16000
        assert buffer.buffer == audio_data
    
    def test_append_numpy_array(self):
        """Test appending numpy array."""
        buffer = AudioBuffer()
        audio_data = np.array([0.1, 0.2, -0.1, -0.2], dtype=np.float32)
        
        buffer.append(audio_data)
        assert len(buffer.buffer) == 4
        assert buffer.buffer == audio_data.tolist()
    
    def test_append_empty_data(self):
        """Test appending empty data."""
        buffer = AudioBuffer()
        buffer.append([])
        assert len(buffer.buffer) == 0
    
    def test_append_invalid_data(self):
        """Test appending invalid data types."""
        buffer = AudioBuffer()
        
        with pytest.raises(AudioProcessingError):
            buffer.append("invalid")
        
        with pytest.raises(AudioProcessingError):
            buffer.append([1, 2, "invalid"])
    
    def test_append_clipping(self):
        """Test audio data is clipped to valid range."""
        buffer = AudioBuffer()
        audio_data = [2.0, -2.0, 0.5]  # Values outside [-1, 1]
        
        buffer.append(audio_data)
        assert buffer.buffer == [1.0, -1.0, 0.5]  # Clipped values
    
    def test_extract_segment_full(self):
        """Test extracting full segment."""
        buffer = AudioBuffer()
        audio_data = list(range(10))
        buffer.append(audio_data)
        
        segment = buffer.extract_segment(duration=None, start_index=0)
        assert segment == audio_data
        assert len(buffer.buffer) == 10  # Original buffer unchanged
    
    def test_extract_segment_partial(self):
        """Test extracting partial segment."""
        buffer = AudioBuffer(sample_rate=10)  # 10 Hz for easy calculation
        audio_data = list(range(20))
        buffer.append(audio_data)
        
        # Extract 1 second (10 samples) starting from index 5
        segment = buffer.extract_segment(duration=1.0, start_index=5)
        assert len(segment) == 10
        assert segment == list(range(5, 15))
    
    def test_extract_segment_remove_extracted(self):
        """Test extracting segment with removal."""
        buffer = AudioBuffer()
        audio_data = list(range(10))
        buffer.append(audio_data)
        
        segment = buffer.extract_segment(
            duration=None, 
            start_index=3, 
            remove_extracted=True
        )
        assert segment == list(range(3, 10))
        assert buffer.buffer == list(range(3))  # Only first 3 elements remain
    
    def test_extract_recent(self):
        """Test extracting recent audio."""
        buffer = AudioBuffer(sample_rate=10)
        audio_data = list(range(20))
        buffer.append(audio_data)
        
        # Extract last 1 second (10 samples)
        recent = buffer.extract_recent(duration=1.0)
        assert len(recent) == 10
        assert recent == list(range(10, 20))
    
    def test_trim_old_data(self):
        """Test trimming old audio data."""
        buffer = AudioBuffer(sample_rate=10)
        audio_data = list(range(30))
        buffer.append(audio_data)
        
        # Keep only last 1 second (10 samples)
        buffer.trim_old_data(max_duration=1.0)
        assert len(buffer.buffer) == 10
        assert buffer.buffer == list(range(20, 30))
    
    def test_get_rms_level(self):
        """Test RMS level calculation."""
        buffer = AudioBuffer()
        
        # Test silence
        buffer.append([0.0, 0.0, 0.0, 0.0])
        assert buffer.get_rms_level() == 0.0
        
        # Test known values
        buffer.clear()
        buffer.append([0.5, -0.5, 0.5, -0.5])
        expected_rms = 0.5  # RMS of ±0.5 is 0.5
        assert abs(buffer.get_rms_level() - expected_rms) < 0.001
    
    def test_get_peak_level(self):
        """Test peak level calculation."""
        buffer = AudioBuffer()
        buffer.append([0.1, -0.8, 0.6, -0.3])
        
        assert buffer.get_peak_level() == 0.8
    
    def test_to_numpy(self):
        """Test conversion to numpy array."""
        buffer = AudioBuffer()
        audio_data = [0.1, 0.2, -0.1, -0.2]
        buffer.append(audio_data)
        
        # Default float32
        array = buffer.to_numpy()
        assert isinstance(array, np.ndarray)
        assert array.dtype == np.float32
        assert array.tolist() == audio_data
        
        # Specific dtype
        array_int = buffer.to_numpy(dtype=np.int16)
        assert array_int.dtype == np.int16
    
    def test_get_stats(self):
        """Test getting buffer statistics."""
        buffer = AudioBuffer(sample_rate=8000)
        audio_data = [0.5, -0.5, 0.5, -0.5]
        buffer.append(audio_data)
        
        stats = buffer.get_stats()
        
        assert stats["buffer_length"] == 4
        assert stats["duration_seconds"] == 4.0 / 8000
        assert stats["sample_rate"] == 8000
        assert stats["rms_level"] == 0.5
        assert stats["peak_level"] == 0.5
        assert "buffer_start_time" in stats
        assert "last_access_time" in stats
    
    def test_clear(self):
        """Test clearing buffer."""
        buffer = AudioBuffer()
        buffer.append([1, 2, 3, 4])
        
        buffer.clear()
        assert len(buffer.buffer) == 0
        assert buffer.get_duration() == 0.0