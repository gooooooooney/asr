"""Transcription API endpoints."""

import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
import structlog

from asr_api_service.config import settings
from asr_api_service.core.asr.whisper import WhisperASRProvider
from asr_api_service.exceptions import ASRServiceError, ValidationError
from asr_api_service.models.transcription import TranscriptionRequest, TranscriptionResponse
from asr_api_service.utils.validation import validate_audio_file, validate_audio_data

router = APIRouter()
logger = structlog.get_logger(__name__)


async def get_asr_provider() -> WhisperASRProvider:
    """Get configured ASR provider."""
    api_key = settings.get_asr_api_key()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ASR API key not configured"
        )
    
    return WhisperASRProvider(
        api_key=api_key,
        api_url=settings.get_asr_api_url(),
        model=settings.get_asr_model(),
        timeout=30.0,
    )


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    prompt: str = Form("", description="Optional prompt to guide transcription"),
    language: Optional[str] = Form(None, description="Target language code"),
    enable_llm: bool = Form(False, description="Enable LLM-based text correction"),
    asr_provider: WhisperASRProvider = Depends(get_asr_provider),
):
    """Transcribe an uploaded audio file.
    
    Supports common audio formats: WAV, MP3, MP4, M4A, OGG, FLAC, AAC.
    """
    start_time = time.time()
    
    try:
        # Validate uploaded file
        validate_audio_file(audio)
        
        logger.info(
            "Transcription request received",
            filename=audio.filename,
            content_type=audio.content_type,
            size=getattr(audio, 'size', None),
            enable_llm=enable_llm,
        )
        
        # Read audio file
        audio_content = await audio.read()
        
        # For now, we'll need to convert the audio file to the expected format
        # In a full implementation, you'd use a library like librosa or pydub
        # to decode various audio formats to raw PCM data
        
        # This is a simplified implementation that assumes the audio is already
        # in the correct format or can be processed by the ASR provider directly
        
        # TODO: Implement proper audio file decoding
        # For now, we'll raise an error for non-WAV files
        if not audio.filename.lower().endswith('.wav'):
            raise HTTPException(
                status_code=400,
                detail="Only WAV files are currently supported. Full format support coming soon."
            )
        
        # For WAV files, we'd need to extract the audio data
        # This is a placeholder - you'd implement proper WAV parsing
        # or use a library like scipy.io.wavfile.read()
        
        raise HTTPException(
            status_code=501,
            detail="Audio file transcription not yet implemented. Use streaming API for now."
        )
        
    except ValidationError as e:
        logger.warning("Validation error", error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    
    except ASRServiceError as e:
        logger.error("ASR service error", error=e.message, error_code=e.error_code)
        raise HTTPException(status_code=500, detail=e.message)
    
    except Exception as e:
        logger.exception("Unexpected error during transcription")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/transcribe-raw", response_model=TranscriptionResponse)
async def transcribe_raw_audio(
    request: TranscriptionRequest,
    audio_data: list[float],
    sample_rate: int = 16000,
    asr_provider: WhisperASRProvider = Depends(get_asr_provider),
):
    """Transcribe raw audio data provided as JSON.
    
    This endpoint accepts raw audio samples directly, which is useful
    for applications that have already processed audio into float arrays.
    """
    start_time = time.time()
    
    try:
        logger.info(
            "Raw audio transcription request",
            audio_length=len(audio_data),
            sample_rate=sample_rate,
            enable_llm=request.enable_llm,
        )
        
        # Validate audio data
        validation_result = validate_audio_data(
            audio_data, 
            sample_rate,
            min_duration=settings.audio_min_duration,
            max_duration=settings.audio_max_duration,
        )
        
        if not validation_result.is_valid:
            raise ValidationError(
                f"Audio validation failed: {'; '.join(validation_result.errors)}",
                field="audio_data",
                value=f"{len(audio_data)} samples",
            )
        
        # Log warnings
        for warning in validation_result.warnings:
            logger.warning("Audio validation warning", warning=warning)
        
        # Perform transcription
        asr_result = await asr_provider.transcribe(
            audio_data=audio_data,
            sample_rate=sample_rate,
            prompt=request.prompt,
            language=request.language,
        )
        
        # TODO: Implement LLM correction if enabled
        corrected_text = None
        if request.enable_llm and asr_result.text:
            logger.info("LLM correction requested but not yet implemented")
            # corrected_text = await llm_provider.correct(asr_result.text)
        
        # Create response
        response = TranscriptionResponse(
            text=asr_result.text,
            corrected_text=corrected_text,
            confidence=asr_result.confidence,
            processing_time_ms=asr_result.processing_time_ms or 0,
            audio_duration=validation_result.duration,
            model=settings.get_asr_model(),
            provider=settings.asr_provider,
            metadata={
                **asr_result.metadata,
                "validation_warnings": validation_result.warnings,
                "rms_level": validation_result.rms_level,
                "peak_level": validation_result.peak_level,
            },
        )
        
        total_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Transcription completed",
            text_length=len(response.text),
            total_time_ms=total_time_ms,
            asr_time_ms=response.processing_time_ms,
        )
        
        return response
        
    except ValidationError as e:
        logger.warning("Validation error", error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    
    except ASRServiceError as e:
        logger.error("ASR service error", error=e.message, error_code=e.error_code)
        raise HTTPException(status_code=500, detail=e.message)
    
    except Exception as e:
        logger.exception("Unexpected error during transcription")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models")
async def list_models():
    """List available ASR models."""
    return {
        "models": [
            {
                "id": settings.get_asr_model(),
                "provider": settings.asr_provider,
                "description": f"{settings.asr_provider.title()} ASR model",
                "languages": ["en", "zh", "es", "fr", "de", "ja", "ko"],  # Common languages
                "sample_rates": [16000, 22050, 44100],
            }
        ],
        "default_model": settings.get_asr_model(),
        "provider": settings.asr_provider,
    }


@router.get("/test-connection")
async def test_asr_connection(asr_provider: WhisperASRProvider = Depends(get_asr_provider)):
    """Test connection to the ASR provider."""
    try:
        success, message = await asr_provider.test_connection()
        
        return {
            "success": success,
            "message": message,
            "provider": settings.asr_provider,
            "model": settings.get_asr_model(),
            "api_url": settings.get_asr_api_url(),
        }
        
    except Exception as e:
        logger.exception("Failed to test ASR connection")
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}",
            "provider": settings.asr_provider,
        }