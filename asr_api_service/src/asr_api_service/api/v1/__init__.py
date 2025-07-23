"""API v1 package."""

from fastapi import APIRouter

from asr_api_service.api.v1.health import router as health_router
from asr_api_service.api.v1.transcription import router as transcription_router
from asr_api_service.api.v1.streaming import router as streaming_router
from asr_api_service.api.v1.vad import router as vad_router
from asr_api_service.api.v1.mobile import router as mobile_router
from asr_api_service.api.v1.stream_vad import router as stream_vad_router

# API v1 router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(transcription_router, tags=["transcription"])
api_router.include_router(streaming_router, tags=["streaming"])
api_router.include_router(vad_router, tags=["vad"])
api_router.include_router(mobile_router, tags=["mobile"])
api_router.include_router(stream_vad_router, tags=["streaming-vad"])

__all__ = ["api_router"]