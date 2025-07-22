"""Health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from asr_api_service.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    version: str
    settings: dict


class DetailedHealthResponse(BaseModel):
    """Detailed health check response model."""

    status: str
    service: str
    version: str
    settings: dict
    checks: dict


@router.get("/health", response_model=HealthResponse)
async def basic_health_check():
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="asr-api-service",
        version="0.1.0",
        settings={
            "asr_provider": settings.asr_provider,
            "llm_provider": settings.llm_provider,
            "audio_sample_rate": settings.audio_sample_rate,
            "vad_threshold": settings.vad_threshold,
        },
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """Detailed health check endpoint with system checks."""
    checks = {}
    
    # Check storage directories
    checks["storage"] = {
        "audio_storage": settings.audio_storage_path.exists() and settings.audio_storage_path.is_dir(),
        "log_storage": settings.log_storage_path.exists() and settings.log_storage_path.is_dir(),
        "temp_storage": settings.temp_storage_path.exists() and settings.temp_storage_path.is_dir(),
    }
    
    # Check API keys
    checks["api_keys"] = {
        "asr_key_configured": bool(settings.get_asr_api_key()),
        "llm_key_configured": bool(settings.llm_api_key),
    }
    
    # Check configuration
    checks["configuration"] = {
        "valid_vad_threshold": 0.0 <= settings.vad_threshold <= 1.0,
        "valid_audio_settings": settings.audio_sample_rate > 0 and settings.audio_chunk_duration > 0,
    }
    
    # Overall status
    all_checks_passed = all(
        all(check_results.values()) if isinstance(check_results, dict) else check_results
        for check_results in checks.values()
    )
    
    return DetailedHealthResponse(
        status="healthy" if all_checks_passed else "degraded",
        service="asr-api-service",
        version="0.1.0",
        settings={
            "asr_provider": settings.asr_provider,
            "llm_provider": settings.llm_provider,
            "audio_sample_rate": settings.audio_sample_rate,
            "vad_threshold": settings.vad_threshold,
            "streaming_max_clients": settings.streaming_max_clients,
        },
        checks=checks,
    )


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes."""
    # Check if required API keys are configured
    asr_key = settings.get_asr_api_key()
    if not asr_key:
        return {"status": "not ready", "reason": "ASR API key not configured"}
    
    # Check storage directories
    if not settings.audio_storage_path.exists():
        return {"status": "not ready", "reason": "Audio storage directory not available"}
    
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Liveness check endpoint for Kubernetes."""
    return {"status": "alive"}