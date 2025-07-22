"""API v1 package."""

from fastapi import APIRouter

from asr_api_service.api.v1.health import router as health_router
from asr_api_service.api.v1.transcription import router as transcription_router
from asr_api_service.api.v1.streaming import router as streaming_router

# API v1 router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(transcription_router, tags=["transcription"])
api_router.include_router(streaming_router, tags=["streaming"])

__all__ = ["api_router"]