"""Audio-related Pydantic models."""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class AudioMetadata(BaseModel):
    """Audio metadata information."""
    
    sample_rate: int = Field(
        default=16000,
        description="Audio sample rate in Hz",
        ge=8000,
        le=48000,
    )
    channels: int = Field(
        default=1,
        description="Number of audio channels",
        ge=1,
        le=8,
    )
    duration: Optional[float] = Field(
        default=None,
        description="Audio duration in seconds",
        ge=0.0,
    )
    format: Optional[str] = Field(
        default=None,
        description="Audio format (wav, mp3, etc.)",
    )
    bitrate: Optional[int] = Field(
        default=None,
        description="Audio bitrate",
        ge=8000,
    )
    
    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        """Validate sample rate is supported."""
        supported_rates = [8000, 16000, 22050, 44100, 48000]
        if v not in supported_rates:
            raise ValueError(f"Sample rate must be one of: {supported_rates}")
        return v


class AudioProcessingRequest(BaseModel):
    """Audio processing request."""
    
    audio_data: List[float] = Field(
        description="Audio samples as float32 values between -1.0 and 1.0"
    )
    metadata: AudioMetadata = Field(
        default_factory=AudioMetadata,
        description="Audio metadata",
    )
    
    @field_validator("audio_data")
    @classmethod
    def validate_audio_data(cls, v: List[float]) -> List[float]:
        """Validate audio data."""
        if not v:
            raise ValueError("Audio data cannot be empty")
        
        if len(v) > 16000 * 300:  # Max 5 minutes at 16kHz
            raise ValueError("Audio data too long (max 5 minutes)")
        
        # Check for reasonable audio values
        if any(abs(sample) > 2.0 for sample in v):
            raise ValueError("Audio samples should be between -1.0 and 1.0")
            
        return v
        
    @property
    def duration(self) -> float:
        """Calculate audio duration in seconds."""
        return len(self.audio_data) / self.metadata.sample_rate
        
    def get_rms_level(self) -> float:
        """Calculate RMS level of audio."""
        if not self.audio_data:
            return 0.0
        squares = [sample ** 2 for sample in self.audio_data]
        mean_square = sum(squares) / len(squares)
        return mean_square ** 0.5
        
    def get_peak_level(self) -> float:
        """Get peak amplitude level."""
        if not self.audio_data:
            return 0.0
        return max(abs(sample) for sample in self.audio_data)


class AudioValidationResult(BaseModel):
    """Audio validation result."""
    
    is_valid: bool = Field(description="Whether audio is valid")
    duration: float = Field(description="Audio duration in seconds")
    sample_rate: int = Field(description="Audio sample rate")
    channels: int = Field(description="Number of channels")
    rms_level: float = Field(description="RMS audio level")
    peak_level: float = Field(description="Peak audio level")
    is_silent: bool = Field(description="Whether audio appears to be silent")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")