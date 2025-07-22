"""Transcription-related Pydantic models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from asr_api_service.models.audio import AudioMetadata


class TranscriptionSegment(BaseModel):
    """A segment of transcribed text with timing information."""
    
    id: int = Field(description="Segment ID")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds") 
    text: str = Field(description="Transcribed text for this segment")
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )


class TranscriptionRequest(BaseModel):
    """Request for audio transcription."""
    
    # Audio data can be provided as base64 or file upload (handled separately)
    prompt: str = Field(
        default="",
        description="Optional prompt to guide transcription",
        max_length=1000,
    )
    language: Optional[str] = Field(
        default=None,
        description="Target language code (e.g., 'en', 'zh', 'es')",
        pattern=r"^[a-z]{2}$",
    )
    enable_llm: bool = Field(
        default=False,
        description="Enable LLM-based text correction",
    )
    enable_timestamps: bool = Field(
        default=False,
        description="Include timing information in response",
    )
    audio_metadata: Optional[AudioMetadata] = Field(
        default=None,
        description="Audio metadata if known",
    )


class TranscriptionResponse(BaseModel):
    """Response from transcription service."""
    
    text: str = Field(description="Complete transcribed text")
    corrected_text: Optional[str] = Field(
        default=None,
        description="LLM-corrected text (if enabled)",
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Overall confidence score",
        ge=0.0,
        le=1.0,
    )
    segments: List[TranscriptionSegment] = Field(
        default_factory=list,
        description="Individual text segments with timing",
    )
    processing_time_ms: int = Field(
        description="Processing time in milliseconds",
        ge=0,
    )
    audio_duration: float = Field(
        description="Audio duration in seconds",
        ge=0.0,
    )
    model: str = Field(description="ASR model used")
    provider: str = Field(description="ASR provider used")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


class BatchTranscriptionRequest(BaseModel):
    """Request for batch transcription of multiple audio files."""
    
    files: List[str] = Field(description="List of audio file paths or IDs")
    common_settings: TranscriptionRequest = Field(
        description="Common settings for all files",
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for completion notification",
    )


class BatchTranscriptionResponse(BaseModel):
    """Response for batch transcription."""
    
    batch_id: str = Field(description="Unique batch identifier")
    status: str = Field(description="Batch status (pending, processing, completed, failed)")
    total_files: int = Field(description="Total number of files in batch")
    completed_files: int = Field(description="Number of completed files")
    results: List[TranscriptionResponse] = Field(
        default_factory=list,
        description="Completed transcription results",
    )
    estimated_completion_time: Optional[float] = Field(
        default=None,
        description="Estimated completion time in seconds",
    )