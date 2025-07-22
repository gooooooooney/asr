"""Custom exceptions for the ASR API service."""

from typing import Any, Dict, Optional


class ASRServiceError(Exception):
    """Base exception for ASR service errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format."""
        return {
            "error": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }


class ConfigurationError(ASRServiceError):
    """Raised when there are configuration issues."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details={"config_key": config_key} if config_key else {},
        )


class AudioProcessingError(ASRServiceError):
    """Raised when audio processing fails."""

    def __init__(self, message: str, audio_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="AUDIO_PROCESSING_ERROR",
            details=audio_info or {},
        )


class ASRProviderError(ASRServiceError):
    """Raised when ASR provider API calls fail."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code="ASR_PROVIDER_ERROR",
            details={
                "provider": provider,
                "status_code": status_code,
                "response_data": response_data,
            },
        )


class LLMProviderError(ASRServiceError):
    """Raised when LLM provider API calls fail."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code="LLM_PROVIDER_ERROR",
            details={
                "provider": provider,
                "status_code": status_code,
                "response_data": response_data,
            },
        )


class StreamingError(ASRServiceError):
    """Raised when streaming operations fail."""

    def __init__(self, message: str, client_id: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="STREAMING_ERROR",
            details={"client_id": client_id} if client_id else {},
        )


class VADError(ASRServiceError):
    """Raised when VAD processing fails."""

    def __init__(self, message: str, vad_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VAD_ERROR",
            details=vad_info or {},
        )


class ValidationError(ASRServiceError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, "value": str(value) if value is not None else None},
        )


class StorageError(ASRServiceError):
    """Raised when storage operations fail."""

    def __init__(self, message: str, path: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            details={"path": path} if path else {},
        )