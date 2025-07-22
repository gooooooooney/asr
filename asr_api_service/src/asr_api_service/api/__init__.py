"""API package for ASR API Service."""

from fastapi import APIRouter

from asr_api_service.api.v1 import api_router as v1_router

# Main API router
api_router = APIRouter()

# Include v1 API
api_router.include_router(v1_router, prefix="/api/v1", tags=["v1"])

__all__ = ["api_router"]