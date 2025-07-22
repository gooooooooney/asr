"""Whisper ASR provider implementation."""

import tempfile
import time
import wave
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
import numpy as np
import structlog

from asr_api_service.core.asr.base import ASRProvider, ASRResult
from asr_api_service.exceptions import ASRProviderError

logger = structlog.get_logger(__name__)


class WhisperASRProvider(ASRProvider):
    """Whisper ASR provider supporting OpenAI and Fireworks APIs."""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        model: str = "whisper-1",
        timeout: float = 30.0,
    ):
        """Initialize Whisper ASR provider.
        
        Args:
            api_key: API key for the service
            api_url: API endpoint URL
            model: Whisper model name
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, api_url, model)
        self.timeout = timeout
        
    async def transcribe(
        self,
        audio_data: List[float],
        sample_rate: int = 16000,
        prompt: str = "",
        language: Optional[str] = None,
        **kwargs
    ) -> ASRResult:
        """Transcribe audio using Whisper API.
        
        Args:
            audio_data: Audio samples
            sample_rate: Audio sample rate
            prompt: Context prompt for better recognition
            language: Target language code (e.g., 'en', 'zh')
            **kwargs: Additional options
            
        Returns:
            ASR transcription result
            
        Raises:
            ASRProviderError: If transcription fails
        """
        start_time = time.time()
        
        try:
            # Validate input
            self.validate_audio_data(audio_data)
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                wav_path = tmp_file.name
                
            try:
                # Write audio to WAV file
                self._write_wav_file(wav_path, audio_data, sample_rate)
                
                # Prepare API request
                files = {"file": open(wav_path, "rb")}
                data = self._prepare_request_data(prompt, language, **kwargs)
                
                # Make API request
                result = await self._make_api_request(files, data)
                
                # Process response
                text = self._extract_text_from_response(result)
                
            finally:
                # Cleanup
                if "file" in locals():
                    files["file"].close()
                Path(wav_path).unlink(missing_ok=True)
                
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(
                "Transcription completed",
                text_length=len(text),
                processing_time_ms=processing_time_ms,
                model=self.model,
            )
            
            return ASRResult(
                text=text,
                processing_time_ms=processing_time_ms,
                metadata={
                    "model": self.model,
                    "provider": self.get_provider_name(),
                    "sample_rate": sample_rate,
                    "audio_duration": len(audio_data) / sample_rate,
                }
            )
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Transcription failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time_ms,
            )
            
            if isinstance(e, ASRProviderError):
                raise
            else:
                raise ASRProviderError(
                    f"Whisper transcription failed: {str(e)}",
                    provider=self.get_provider_name(),
                )

    def _write_wav_file(self, filepath: str, audio_data: List[float], sample_rate: int) -> None:
        """Write audio data to WAV file.
        
        Args:
            filepath: Output file path
            audio_data: Audio samples
            sample_rate: Audio sample rate
        """
        audio_int16 = self.create_audio_array(audio_data, sample_rate, np.int16)
        
        with wave.open(filepath, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

    def _prepare_request_data(
        self, 
        prompt: str, 
        language: Optional[str],
        **kwargs
    ) -> Dict[str, str]:
        """Prepare API request data.
        
        Args:
            prompt: Context prompt
            language: Target language code
            **kwargs: Additional options
            
        Returns:
            Request data dictionary
        """
        data = {
            "model": self.model,
            "response_format": "verbose_json",
            "timestamp_granularities": "segment",
        }
        
        # Add optional parameters
        if prompt:
            data["prompt"] = prompt
            
        if language:
            data["language"] = language
            
        # Provider-specific parameters
        if "fireworks" in self.api_url.lower():
            data.update({
                "vad_model": "silero",
                "temperature": "0.0",
            })
            
        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in data:  # Don't override defaults
                data[key] = str(value)
                
        return data

    async def _make_api_request(self, files: dict, data: dict) -> dict:
        """Make API request to transcription service.
        
        Args:
            files: Files to upload
            data: Request data
            
        Returns:
            API response data
            
        Raises:
            ASRProviderError: If API request fails
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    files=files,
                    data=data,
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_detail = None
                    try:
                        error_detail = response.json()
                    except:
                        error_detail = response.text
                        
                    raise ASRProviderError(
                        f"API request failed with status {response.status_code}",
                        provider=self.get_provider_name(),
                        status_code=response.status_code,
                        response_data=error_detail,
                    )
                    
            except httpx.TimeoutException:
                raise ASRProviderError(
                    "API request timed out",
                    provider=self.get_provider_name(),
                )
            except httpx.RequestError as e:
                raise ASRProviderError(
                    f"API request error: {str(e)}",
                    provider=self.get_provider_name(),
                )

    def _extract_text_from_response(self, response_data: dict) -> str:
        """Extract text from API response.
        
        Args:
            response_data: API response data
            
        Returns:
            Transcribed text
            
        Raises:
            ASRProviderError: If response format is invalid
        """
        try:
            # Try to get text directly
            text = response_data.get("text", "")
            
            # If no direct text, try to extract from segments
            if not text and "segments" in response_data:
                segments = response_data.get("segments", [])
                text = " ".join(segment.get("text", "") for segment in segments)
                
            return text.strip()
            
        except Exception as e:
            raise ASRProviderError(
                f"Failed to extract text from response: {str(e)}",
                provider=self.get_provider_name(),
                response_data=response_data,
            )

    async def test_connection(self) -> tuple[bool, str]:
        """Test connection to Whisper API.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Create a short silent audio for testing
            duration = 1.0
            sample_rate = 16000
            samples = int(duration * sample_rate)
            silent_audio = [0.0] * samples
            
            # Add a small amount of noise to avoid completely silent audio
            silent_audio[samples // 2] = 0.001
            
            # Try transcription
            result = await self.transcribe(silent_audio, sample_rate)
            
            return True, f"Connection successful. Response: '{result.text[:50]}...'"
            
        except ASRProviderError as e:
            return False, f"API error: {e.message}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"