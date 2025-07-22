"""ASR API Service - Modern speech recognition API with streaming capabilities."""

__version__ = "0.1.0"
__author__ = "Meeting Code Team"
__email__ = "team@meetingcode.dev"
__description__ = "Modern ASR API Service with VAD and streaming capabilities"

from asr_api_service.exceptions import ASRServiceError, ConfigurationError

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__",
    "ASRServiceError",
    "ConfigurationError",
]