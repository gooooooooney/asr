"""Unit tests for configuration."""

import pytest
from pathlib import Path

from asr_api_service.config import Settings, ASRProvider, LLMProvider, LogLevel, LogFormat


class TestSettings:
    """Test cases for Settings class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        settings = Settings()
        
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.api_workers == 1
        assert not settings.api_reload
        assert not settings.api_debug
        
        assert settings.asr_provider == ASRProvider.WHISPER
        assert settings.llm_provider == LLMProvider.FIREWORKS
        
        assert settings.vad_threshold == 0.5
        assert settings.vad_silence_duration == 0.8
        assert settings.vad_hop_size == 256
        
        assert settings.audio_sample_rate == 16000
        assert settings.audio_chunk_duration == 3.0
        assert settings.audio_lookback_duration == 9.0
        
        assert settings.log_level == LogLevel.INFO
        assert settings.log_format == LogFormat.JSON
    
    def test_path_creation(self):
        """Test that storage paths are created."""
        settings = Settings(
            audio_storage_path="./test_audio",
            log_storage_path="./test_logs",
            temp_storage_path="./test_temp"
        )
        
        assert settings.audio_storage_path.exists()
        assert settings.log_storage_path.exists()
        assert settings.temp_storage_path.exists()
        
        # Clean up
        settings.audio_storage_path.rmdir()
        settings.log_storage_path.rmdir()
        settings.temp_storage_path.rmdir()
    
    def test_vad_threshold_validation(self):
        """Test VAD threshold validation."""
        # Valid threshold
        settings = Settings(vad_threshold=0.7)
        assert settings.vad_threshold == 0.7
        
        # Invalid thresholds should raise validation error
        with pytest.raises(ValueError):
            Settings(vad_threshold=-0.1)
        
        with pytest.raises(ValueError):
            Settings(vad_threshold=1.5)
    
    def test_port_validation(self):
        """Test port number validation."""
        # Valid port
        settings = Settings(api_port=8080)
        assert settings.api_port == 8080
        
        # Invalid ports
        with pytest.raises(ValueError):
            Settings(api_port=0)
        
        with pytest.raises(ValueError):
            Settings(api_port=70000)
    
    def test_duration_validation(self):
        """Test audio duration validation."""
        # Valid durations
        settings = Settings(
            audio_chunk_duration=5.0,
            audio_lookback_duration=10.0,
            audio_max_duration=600.0
        )
        assert settings.audio_chunk_duration == 5.0
        assert settings.audio_lookback_duration == 10.0
        assert settings.audio_max_duration == 600.0
        
        # Invalid durations
        with pytest.raises(ValueError):
            Settings(audio_chunk_duration=-1.0)
        
        with pytest.raises(ValueError):
            Settings(audio_lookback_duration=0.0)
    
    def test_get_asr_api_key(self):
        """Test ASR API key retrieval."""
        # Whisper provider
        settings = Settings(
            asr_provider=ASRProvider.WHISPER,
            whisper_api_key="whisper-key"
        )
        assert settings.get_asr_api_key() == "whisper-key"
        
        # OpenAI provider
        settings = Settings(
            asr_provider=ASRProvider.OPENAI,
            openai_api_key="openai-key"
        )
        assert settings.get_asr_api_key() == "openai-key"
        
        # Fireworks provider
        settings = Settings(
            asr_provider=ASRProvider.FIREWORKS,
            fireworks_api_key="fireworks-key"
        )
        assert settings.get_asr_api_key() == "fireworks-key"
    
    def test_get_asr_api_url(self):
        """Test ASR API URL retrieval."""
        # Default Whisper URL
        settings = Settings(asr_provider=ASRProvider.WHISPER)
        assert "openai.com" in settings.get_asr_api_url()
        
        # Fireworks URL
        settings = Settings(asr_provider=ASRProvider.FIREWORKS)
        assert "fireworks.ai" in settings.get_asr_api_url()
    
    def test_get_asr_model(self):
        """Test ASR model name retrieval."""
        settings = Settings(
            asr_provider=ASRProvider.WHISPER,
            whisper_model="whisper-large"
        )
        assert settings.get_asr_model() == "whisper-large"
        
        settings = Settings(
            asr_provider=ASRProvider.FIREWORKS,
            fireworks_model="whisper-v3"
        )
        assert settings.get_asr_model() == "whisper-v3"
    
    def test_is_development(self):
        """Test development mode detection."""
        # Production mode
        settings = Settings(api_debug=False, api_reload=False)
        assert not settings.is_development
        
        # Debug mode
        settings = Settings(api_debug=True, api_reload=False)
        assert settings.is_development
        
        # Reload mode
        settings = Settings(api_debug=False, api_reload=True)
        assert settings.is_development
    
    def test_cors_config(self):
        """Test CORS configuration."""
        settings = Settings(
            api_cors_origins=["http://localhost:3000", "https://example.com"],
            api_cors_methods=["GET", "POST"],
            api_cors_headers=["Content-Type", "Authorization"]
        )
        
        cors_config = settings.cors_config
        
        assert cors_config["allow_origins"] == ["http://localhost:3000", "https://example.com"]
        assert cors_config["allow_methods"] == ["GET", "POST"]
        assert cors_config["allow_headers"] == ["Content-Type", "Authorization"]
        assert cors_config["allow_credentials"] is True