"""Audio validation utilities."""

import mimetypes
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
from fastapi import UploadFile

from asr_api_service.exceptions import ValidationError
from asr_api_service.models.audio import AudioValidationResult


def validate_audio_file(file: UploadFile, max_size_mb: int = 25) -> None:
    """Validate uploaded audio file.
    
    Args:
        file: Uploaded file
        max_size_mb: Maximum file size in MB
        
    Raises:
        ValidationError: If file is invalid
    """
    # Check file size
    if hasattr(file, 'size') and file.size:
        max_size_bytes = max_size_mb * 1024 * 1024
        if file.size > max_size_bytes:
            raise ValidationError(
                f"File size {file.size / 1024 / 1024:.1f}MB exceeds maximum {max_size_mb}MB",
                field="file_size",
                value=file.size,
            )
    
    # Check file type
    if file.content_type:
        if not file.content_type.startswith('audio/'):
            raise ValidationError(
                f"Invalid content type: {file.content_type}. Must be an audio file.",
                field="content_type",
                value=file.content_type,
            )
    
    # Check file extension
    if file.filename:
        suffix = Path(file.filename).suffix.lower()
        allowed_extensions = ['.wav', '.mp3', '.mp4', '.m4a', '.ogg', '.flac', '.aac']
        if suffix not in allowed_extensions:
            raise ValidationError(
                f"Invalid file extension: {suffix}. Allowed: {allowed_extensions}",
                field="file_extension",
                value=suffix,
            )


def validate_audio_data(
    audio_data: List[float],
    sample_rate: int = 16000,
    min_duration: float = 0.1,
    max_duration: float = 300.0,
) -> AudioValidationResult:
    """Validate audio data and return detailed results.
    
    Args:
        audio_data: Audio samples
        sample_rate: Audio sample rate
        min_duration: Minimum duration in seconds
        max_duration: Maximum duration in seconds
        
    Returns:
        Validation result with detailed information
    """
    errors = []
    warnings = []
    
    # Basic validation
    if not audio_data:
        errors.append("Audio data is empty")
        return AudioValidationResult(
            is_valid=False,
            duration=0.0,
            sample_rate=sample_rate,
            channels=1,
            rms_level=0.0,
            peak_level=0.0,
            is_silent=True,
            errors=errors,
            warnings=warnings,
        )
    
    # Calculate metrics
    audio_array = np.array(audio_data, dtype=np.float32)
    duration = len(audio_data) / sample_rate
    rms_level = float(np.sqrt(np.mean(audio_array ** 2)))
    peak_level = float(np.max(np.abs(audio_array)))
    
    # Duration checks
    if duration < min_duration:
        errors.append(f"Audio duration {duration:.2f}s is less than minimum {min_duration}s")
    
    if duration > max_duration:
        errors.append(f"Audio duration {duration:.2f}s exceeds maximum {max_duration}s")
    
    # Audio level checks
    is_silent = rms_level < 1e-6
    if is_silent:
        warnings.append("Audio appears to be completely silent")
    
    if rms_level < 0.001:
        warnings.append("Audio level is very low (possible recording issue)")
    
    if peak_level > 1.0:
        warnings.append("Audio has clipping (peak level > 1.0)")
    
    # Check for reasonable audio values
    if any(abs(sample) > 2.0 for sample in audio_data):
        errors.append("Audio contains samples outside reasonable range (-2.0 to 2.0)")
    
    # Check for NaN or infinite values
    if any(not np.isfinite(sample) for sample in audio_data):
        errors.append("Audio contains NaN or infinite values")
    
    # Sample rate validation
    if sample_rate <= 0:
        errors.append("Sample rate must be positive")
    elif sample_rate < 8000:
        warnings.append("Sample rate is very low (< 8kHz)")
    elif sample_rate > 48000:
        warnings.append("Sample rate is very high (> 48kHz)")
    
    return AudioValidationResult(
        is_valid=len(errors) == 0,
        duration=duration,
        sample_rate=sample_rate,
        channels=1,  # Assume mono for now
        rms_level=rms_level,
        peak_level=peak_level,
        is_silent=is_silent,
        errors=errors,
        warnings=warnings,
    )


def normalize_audio_levels(audio_data: List[float], target_rms: float = 0.1) -> List[float]:
    """Normalize audio levels to target RMS.
    
    Args:
        audio_data: Input audio samples
        target_rms: Target RMS level
        
    Returns:
        Normalized audio samples
    """
    if not audio_data:
        return audio_data
    
    audio_array = np.array(audio_data, dtype=np.float32)
    current_rms = np.sqrt(np.mean(audio_array ** 2))
    
    if current_rms < 1e-6:  # Avoid division by zero
        return audio_data
    
    # Calculate gain factor
    gain = target_rms / current_rms
    
    # Apply gain and clip to prevent overflow
    normalized = audio_array * gain
    normalized = np.clip(normalized, -1.0, 1.0)
    
    return normalized.tolist()


def detect_audio_properties(audio_data: List[float], sample_rate: int) -> dict:
    """Detect various audio properties.
    
    Args:
        audio_data: Audio samples
        sample_rate: Sample rate
        
    Returns:
        Dictionary with detected properties
    """
    if not audio_data:
        return {}
    
    audio_array = np.array(audio_data, dtype=np.float32)
    
    # Basic metrics
    duration = len(audio_data) / sample_rate
    rms_level = float(np.sqrt(np.mean(audio_array ** 2)))
    peak_level = float(np.max(np.abs(audio_array)))
    
    # Dynamic range
    dynamic_range = 20 * np.log10(peak_level / (rms_level + 1e-10))
    
    # Zero crossing rate (approximate measure of speech/music)
    zero_crossings = np.sum(np.diff(np.signbit(audio_array)))
    zero_crossing_rate = zero_crossings / len(audio_array)
    
    # Spectral centroid (brightness measure)
    # Simplified version - more accurate would use FFT
    abs_audio = np.abs(audio_array)
    spectral_centroid = np.sum(abs_audio * np.arange(len(abs_audio))) / (np.sum(abs_audio) + 1e-10)
    
    return {
        "duration": duration,
        "rms_level": rms_level,
        "peak_level": peak_level,
        "dynamic_range_db": float(dynamic_range),
        "zero_crossing_rate": float(zero_crossing_rate),
        "spectral_centroid": float(spectral_centroid),
        "sample_count": len(audio_data),
        "estimated_file_size_kb": len(audio_data) * 4 / 1024,  # 32-bit float
    }


def convert_sample_rate(
    audio_data: List[float],
    input_rate: int,
    output_rate: int,
) -> List[float]:
    """Simple sample rate conversion using linear interpolation.
    
    Note: For production use, consider using a proper resampling library
    like librosa or scipy.signal.resample.
    
    Args:
        audio_data: Input audio samples
        input_rate: Input sample rate
        output_rate: Output sample rate
        
    Returns:
        Resampled audio data
    """
    if not audio_data or input_rate == output_rate:
        return audio_data
    
    audio_array = np.array(audio_data, dtype=np.float32)
    
    # Calculate resampling ratio
    ratio = output_rate / input_rate
    
    # Create new time indices
    input_length = len(audio_array)
    output_length = int(input_length * ratio)
    
    # Linear interpolation
    input_indices = np.arange(input_length)
    output_indices = np.linspace(0, input_length - 1, output_length)
    
    resampled = np.interp(output_indices, input_indices, audio_array)
    
    return resampled.tolist()