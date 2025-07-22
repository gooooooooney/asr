"""Streaming-related Pydantic models."""

from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, field_validator


class StreamingConfig(BaseModel):
    """Configuration for streaming session."""
    
    api_key: str = Field(description="API key for ASR service")
    enable_llm: bool = Field(
        default=False,
        description="Enable LLM-based text correction",
    )
    language: Optional[str] = Field(
        default=None,
        description="Target language code",
        pattern=r"^[a-z]{2}$",
    )
    vad_threshold: Optional[float] = Field(
        default=None,
        description="VAD threshold override",
        ge=0.0,
        le=1.0,
    )
    chunk_duration: Optional[float] = Field(
        default=None,
        description="Audio chunk duration override in seconds",
        ge=0.5,
        le=10.0,
    )


class StreamingAudioData(BaseModel):
    """Audio data for streaming."""
    
    audio_data: List[float] = Field(
        description="Audio samples as float32 values"
    )
    sample_rate: int = Field(
        default=16000,
        description="Audio sample rate",
    )
    
    @field_validator("audio_data")
    @classmethod
    def validate_audio_data(cls, v: List[float]) -> List[float]:
        """Validate audio data."""
        if not v:
            raise ValueError("Audio data cannot be empty")
        
        if len(v) > 16000 * 30:  # Max 30 seconds per chunk
            raise ValueError("Audio chunk too long (max 30 seconds)")
        
        return v


class StreamingControl(BaseModel):
    """Control commands for streaming."""
    
    command: Literal["start", "stop", "reset", "pause", "resume"] = Field(
        description="Control command"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Command parameters",
    )


class StreamingResult(BaseModel):
    """Streaming transcription result."""
    
    segment_id: int = Field(description="Unique segment identifier")
    text: str = Field(description="Transcribed text")
    corrected_text: Optional[str] = Field(
        default=None,
        description="LLM-corrected text",
    )
    is_final: bool = Field(
        default=False,
        description="Whether this is the final result for this segment",
    )
    is_timeout_chunk: bool = Field(
        default=False,
        description="Whether this was generated due to timeout",
    )
    is_reprocessed: bool = Field(
        default=False,
        description="Whether this replaces previous segments",
    )
    replaces_segments: List[int] = Field(
        default_factory=list,
        description="List of segment IDs this result replaces",
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score",
        ge=0.0,
        le=1.0,
    )
    processing_time_ms: int = Field(
        description="Processing time in milliseconds",
        ge=0,
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


class VADStatus(BaseModel):
    """Voice Activity Detection status."""
    
    is_speaking: bool = Field(description="Whether speech is detected")
    current_state: Literal["speech", "silence"] = Field(
        description="Current VAD state"
    )
    state_changed: bool = Field(
        default=False,
        description="Whether state changed from previous",
    )
    probability: float = Field(
        description="VAD probability score",
        ge=0.0,
        le=1.0,
    )
    rms: float = Field(
        description="RMS audio level",
        ge=0.0,
    )
    max_amplitude: float = Field(
        description="Maximum amplitude",
        ge=0.0,
    )
    silence_timeout: bool = Field(
        default=False,
        description="Whether silence timeout was triggered",
    )


class StreamingStatus(BaseModel):
    """Streaming session status."""
    
    status: Literal["connecting", "ready", "processing", "error", "disconnected"] = Field(
        description="Session status"
    )
    vad_state: Optional[VADStatus] = Field(
        default=None,
        description="VAD status information",
    )
    client_id: Optional[str] = Field(
        default=None,
        description="Client session identifier",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional status metadata",
    )


class StreamingError(BaseModel):
    """Streaming error information."""
    
    error: str = Field(description="Error message")
    error_code: str = Field(description="Error code")
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )
    recoverable: bool = Field(
        default=False,
        description="Whether the error is recoverable",
    )


class StreamingMessage(BaseModel):
    """WebSocket message for streaming communication."""
    
    type: Literal["config", "audio", "control", "result", "status", "error"] = Field(
        description="Message type"
    )
    data: Union[
        StreamingConfig,
        StreamingAudioData, 
        StreamingControl,
        StreamingResult,
        StreamingStatus,
        StreamingError,
        Dict[str, Any]
    ] = Field(description="Message data")
    timestamp: int = Field(description="Message timestamp (Unix time in milliseconds)")
    
    @classmethod
    def create_config(cls, config: StreamingConfig) -> "StreamingMessage":
        """Create a config message."""
        import time
        return cls(
            type="config",
            data=config,
            timestamp=int(time.time() * 1000)
        )
    
    @classmethod
    def create_audio(cls, audio_data: StreamingAudioData) -> "StreamingMessage":
        """Create an audio data message."""
        import time
        return cls(
            type="audio", 
            data=audio_data,
            timestamp=int(time.time() * 1000)
        )
    
    @classmethod
    def create_control(cls, control: StreamingControl) -> "StreamingMessage":
        """Create a control message."""
        import time
        return cls(
            type="control",
            data=control,
            timestamp=int(time.time() * 1000)
        )
    
    @classmethod
    def create_result(cls, result: StreamingResult) -> "StreamingMessage":
        """Create a result message."""
        import time
        return cls(
            type="result",
            data=result,
            timestamp=int(time.time() * 1000)
        )
    
    @classmethod
    def create_status(cls, status: StreamingStatus) -> "StreamingMessage":
        """Create a status message.""" 
        import time
        return cls(
            type="status",
            data=status,
            timestamp=int(time.time() * 1000)
        )
    
    @classmethod
    def create_error(cls, error: StreamingError) -> "StreamingMessage":
        """Create an error message."""
        import time
        return cls(
            type="error",
            data=error,
            timestamp=int(time.time() * 1000)
        )