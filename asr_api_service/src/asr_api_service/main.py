"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog

from asr_api_service.api import api_router
from asr_api_service.config import settings
from asr_api_service.exceptions import ASRServiceError
from asr_api_service.utils.logging import setup_logging


# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info(
        "Starting ASR API Service",
        version="0.1.0",
        host=settings.api_host,
        port=settings.api_port,
        debug=settings.api_debug,
    )
    
    # Create storage directories
    settings.audio_storage_path.mkdir(parents=True, exist_ok=True)
    settings.log_storage_path.mkdir(parents=True, exist_ok=True)
    settings.temp_storage_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(
        "Storage directories created",
        audio_path=str(settings.audio_storage_path),
        log_path=str(settings.log_storage_path),
        temp_path=str(settings.temp_storage_path),
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down ASR API Service")


# Create FastAPI application
app = FastAPI(
    title="ASR API Service",
    description="Modern ASR API Service with VAD and streaming capabilities",
    version="0.1.0",
    docs_url=settings.docs_url if settings.enable_docs else None,
    redoc_url=settings.redoc_url if settings.enable_docs else None,
    openapi_url=settings.openapi_url if settings.enable_docs else None,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    **settings.cors_config,
)

# Add trusted host middleware in production
if not settings.is_development:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure based on your deployment
    )


# Global exception handler
@app.exception_handler(ASRServiceError)
async def asr_service_exception_handler(request: Request, exc: ASRServiceError):
    """Handle ASR service exceptions."""
    logger.error(
        "ASR service error",
        error=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        path=request.url.path,
        method=request.method,
    )
    
    return JSONResponse(
        status_code=400,
        content=exc.to_dict(),
    )


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "details": {},
        },
    )


# Add request logging middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests."""
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        query_params=str(request.query_params),
        client_host=request.client.host if request.client else None,
    )
    
    response = await call_next(request)
    
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    )
    
    return response


# Include API routes
app.include_router(api_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "asr-api-service",
        "version": "0.1.0",
        "settings": {
            "asr_provider": settings.asr_provider,
            "llm_provider": settings.llm_provider,
            "audio_sample_rate": settings.audio_sample_rate,
            "vad_threshold": settings.vad_threshold,
        },
    }


# Metrics endpoint (placeholder for Prometheus metrics)
if settings.enable_metrics:
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        # TODO: Implement Prometheus metrics
        return {"message": "Metrics endpoint - implement Prometheus integration"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "asr_api_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
        workers=1 if settings.api_reload else settings.api_workers,
    )