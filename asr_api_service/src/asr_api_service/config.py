"""Configuration management for ASR API Service."""

import os
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Log format enumeration."""

    JSON = "json"
    TEXT = "text"


class ASRProvider(str, Enum):
    """ASR provider enumeration."""

    WHISPER = "whisper"
    OPENAI = "openai"
    FIREWORKS = "fireworks"


class LLMProvider(str, Enum):
    """LLM provider enumeration."""

    OPENAI = "openai"
    FIREWORKS = "fireworks"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host address")
    api_port: int = Field(default=8000, description="API port number")
    api_workers: int = Field(default=1, description="Number of API workers")
    api_reload: bool = Field(default=False, description="Enable auto-reload in development")
    api_debug: bool = Field(default=False, description="Enable debug mode")
    api_cors_origins: List[str] = Field(
        default=["*"], description="CORS allowed origins"
    )
    api_cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"], description="CORS allowed methods"
    )
    api_cors_headers: List[str] = Field(
        default=["*"], description="CORS allowed headers"
    )

    # ASR Configuration
    asr_provider: ASRProvider = Field(default=ASRProvider.WHISPER, description="ASR provider")
    whisper_api_key: Optional[str] = Field(default=None, description="Whisper API key")
    whisper_api_url: str = Field(
        default="https://api.openai.com/v1/audio/transcriptions",
        description="Whisper API URL",
    )
    whisper_model: str = Field(default="whisper-1", description="Whisper model name")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    fireworks_api_key: Optional[str] = Field(default=None, description="Fireworks API key")
    fireworks_api_url: str = Field(
        default="https://audio-prod.us-virginia-1.direct.fireworks.ai/v1/audio/transcriptions",
        description="Fireworks API URL",
    )
    fireworks_model: str = Field(default="whisper-v3", description="Fireworks model name")

    # LLM Configuration
    llm_provider: LLMProvider = Field(default=LLMProvider.FIREWORKS, description="LLM provider")
    llm_api_key: Optional[str] = Field(default=None, description="LLM API key")
    llm_api_url: str = Field(
        default="https://api.fireworks.ai/inference/v1/chat/completions",
        description="LLM API URL",
    )
    llm_model: str = Field(
        default="accounts/fireworks/models/kimi-k2-instruct", description="LLM model name"
    )
    llm_max_tokens: int = Field(default=4096, description="LLM max tokens")
    llm_temperature: float = Field(default=0.6, description="LLM temperature")
    llm_timeout: float = Field(default=30.0, description="LLM request timeout in seconds")

    # VAD Configuration
    vad_threshold: float = Field(default=0.5, description="VAD threshold")
    vad_silence_duration: float = Field(default=0.8, description="VAD silence duration")
    vad_hop_size: int = Field(default=256, description="VAD hop size")

    # Audio Configuration
    audio_sample_rate: int = Field(default=16000, description="Audio sample rate")
    audio_channels: int = Field(default=1, description="Audio channels")
    audio_chunk_duration: float = Field(default=3.0, description="Audio chunk duration in seconds")
    audio_lookback_duration: float = Field(default=9.0, description="Audio lookback duration")
    audio_max_duration: float = Field(default=300.0, description="Maximum audio duration in seconds")
    audio_min_duration: float = Field(default=0.1, description="Minimum audio duration in seconds")

    # Streaming Configuration
    streaming_max_clients: int = Field(default=100, description="Maximum streaming clients")
    streaming_ping_interval: int = Field(default=20, description="WebSocket ping interval")
    streaming_ping_timeout: int = Field(default=10, description="WebSocket ping timeout")
    streaming_close_timeout: int = Field(default=5, description="WebSocket close timeout")

    # Storage Configuration
    audio_storage_path: Path = Field(
        default=Path("./data/audio"), description="Audio storage directory"
    )
    log_storage_path: Path = Field(
        default=Path("./data/logs"), description="Log storage directory"
    )
    temp_storage_path: Path = Field(
        default=Path("./data/temp"), description="Temporary storage directory"
    )

    # Logging Configuration
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    log_format: LogFormat = Field(default=LogFormat.JSON, description="Log format")
    log_file: Optional[Path] = Field(default=None, description="Log file path")
    log_rotation: str = Field(default="100 MB", description="Log rotation size")
    log_retention: str = Field(default="30 days", description="Log retention period")

    # Security Configuration
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT tokens",
    )
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration in minutes"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, description="Rate limit requests per minute")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")

    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_path: str = Field(default="/metrics", description="Metrics endpoint path")
    enable_health_check: bool = Field(default=True, description="Enable health check endpoint")
    health_check_path: str = Field(default="/health", description="Health check endpoint path")

    # Development Configuration
    enable_docs: bool = Field(default=True, description="Enable API documentation")
    docs_url: str = Field(default="/docs", description="API documentation URL")
    redoc_url: str = Field(default="/redoc", description="ReDoc documentation URL")
    openapi_url: str = Field(default="/openapi.json", description="OpenAPI schema URL")

    @field_validator("audio_storage_path", "log_storage_path", "temp_storage_path")
    @classmethod
    def validate_paths(cls, v: Union[str, Path]) -> Path:
        """Validate and create storage paths."""
        path = Path(v) if isinstance(v, str) else v
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("vad_threshold")
    @classmethod
    def validate_vad_threshold(cls, v: float) -> float:
        """Validate VAD threshold is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("VAD threshold must be between 0.0 and 1.0")
        return v

    @field_validator("audio_chunk_duration", "audio_lookback_duration", "audio_max_duration")
    @classmethod
    def validate_positive_duration(cls, v: float) -> float:
        """Validate audio durations are positive."""
        if v <= 0:
            raise ValueError("Audio duration must be positive")
        return v

    @field_validator("api_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    def get_asr_api_key(self) -> Optional[str]:
        """Get the API key for the configured ASR provider."""
        if self.asr_provider == ASRProvider.WHISPER:
            return self.whisper_api_key
        elif self.asr_provider == ASRProvider.OPENAI:
            return self.openai_api_key
        elif self.asr_provider == ASRProvider.FIREWORKS:
            return self.fireworks_api_key
        return None

    def get_asr_api_url(self) -> str:
        """Get the API URL for the configured ASR provider."""
        if self.asr_provider == ASRProvider.WHISPER:
            return self.whisper_api_url
        elif self.asr_provider == ASRProvider.OPENAI:
            return self.whisper_api_url
        elif self.asr_provider == ASRProvider.FIREWORKS:
            return self.fireworks_api_url
        return self.whisper_api_url

    def get_asr_model(self) -> str:
        """Get the model name for the configured ASR provider."""
        if self.asr_provider == ASRProvider.WHISPER:
            return self.whisper_model
        elif self.asr_provider == ASRProvider.OPENAI:
            return self.whisper_model
        elif self.asr_provider == ASRProvider.FIREWORKS:
            return self.fireworks_model
        return self.whisper_model

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.api_debug or self.api_reload

    @property
    def cors_config(self) -> dict:
        """Get CORS configuration."""
        return {
            "allow_origins": self.api_cors_origins,
            "allow_methods": self.api_cors_methods,
            "allow_headers": self.api_cors_headers,
            "allow_credentials": True,
        }


# Global settings instance
settings = Settings()