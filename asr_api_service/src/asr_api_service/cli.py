"""Command-line interface for ASR API Service."""

import os
import sys
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from asr_api_service.config import settings

app = typer.Typer(
    name="asr-api",
    help="ASR API Service - Modern speech recognition API with streaming capabilities",
    no_args_is_help=True,
)
console = Console()


@app.command()
def serve(
    host: str = typer.Option(None, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(None, "--port", "-p", help="Port to bind to"),
    workers: int = typer.Option(None, "--workers", "-w", help="Number of worker processes"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
    log_level: str = typer.Option(None, "--log-level", "-l", help="Log level"),
):
    """Start the ASR API server."""
    # Use settings defaults if not provided
    _host = host or settings.api_host
    _port = port or settings.api_port
    _workers = workers or settings.api_workers
    _log_level = log_level or settings.log_level.lower()
    
    console.print(f"🚀 Starting ASR API Service on {_host}:{_port}", style="bold green")
    console.print(f"📊 Workers: {_workers}", style="dim")
    console.print(f"🔧 Reload: {reload}", style="dim")
    console.print(f"📝 Log Level: {_log_level}", style="dim")
    
    try:
        uvicorn.run(
            "asr_api_service.main:app",
            host=_host,
            port=_port,
            workers=1 if reload else _workers,
            reload=reload,
            log_level=_log_level,
        )
    except KeyboardInterrupt:
        console.print("\n👋 Shutting down ASR API Service", style="yellow")
    except Exception as e:
        console.print(f"❌ Failed to start server: {e}", style="red")
        sys.exit(1)


@app.command()
def config(
    show_secrets: bool = typer.Option(False, "--show-secrets", help="Show secret values"),
):
    """Show current configuration."""
    console.print("🔧 ASR API Service Configuration", style="bold blue")
    
    table = Table(title="Settings")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    table.add_column("Description", style="green")
    
    # API settings
    table.add_row("api_host", settings.api_host, "API host address")
    table.add_row("api_port", str(settings.api_port), "API port number")
    table.add_row("api_workers", str(settings.api_workers), "Number of API workers")
    table.add_row("api_debug", str(settings.api_debug), "Debug mode")
    table.add_row("api_reload", str(settings.api_reload), "Auto-reload")
    
    # ASR settings
    table.add_row("asr_provider", settings.asr_provider, "ASR provider")
    asr_key = settings.get_asr_api_key()
    if asr_key and not show_secrets:
        asr_key = f"{asr_key[:8]}...{asr_key[-4:]}" if len(asr_key) > 12 else "***"
    table.add_row("asr_api_key", asr_key or "Not set", "ASR API key")
    table.add_row("asr_model", settings.get_asr_model(), "ASR model")
    
    # LLM settings
    table.add_row("llm_provider", settings.llm_provider, "LLM provider")
    llm_key = settings.llm_api_key
    if llm_key and not show_secrets:
        llm_key = f"{llm_key[:8]}...{llm_key[-4:]}" if len(llm_key) > 12 else "***"
    table.add_row("llm_api_key", llm_key or "Not set", "LLM API key")
    table.add_row("llm_model", settings.llm_model, "LLM model")
    
    # Audio settings
    table.add_row("audio_sample_rate", str(settings.audio_sample_rate), "Audio sample rate")
    table.add_row("audio_chunk_duration", str(settings.audio_chunk_duration), "Audio chunk duration")
    table.add_row("vad_threshold", str(settings.vad_threshold), "VAD threshold")
    table.add_row("vad_silence_duration", str(settings.vad_silence_duration), "VAD silence duration")
    
    # Storage settings
    table.add_row("audio_storage_path", str(settings.audio_storage_path), "Audio storage path")
    table.add_row("log_storage_path", str(settings.log_storage_path), "Log storage path")
    
    console.print(table)


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Check system requirements and configuration."""
    console.print("🔍 Checking ASR API Service", style="bold blue")
    
    checks = []
    
    # Check Python version
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    python_ok = sys.version_info >= (3, 9)
    checks.append(("Python Version", python_version, python_ok, "Requires Python 3.9+"))
    
    # Check storage directories
    for name, path in [
        ("Audio Storage", settings.audio_storage_path),
        ("Log Storage", settings.log_storage_path),
        ("Temp Storage", settings.temp_storage_path),
    ]:
        exists = path.exists() and path.is_dir()
        writable = exists and os.access(path, os.W_OK) if exists else False
        checks.append((name, str(path), exists and writable, "Directory must exist and be writable"))
    
    # Check API keys
    asr_key = settings.get_asr_api_key()
    checks.append(("ASR API Key", "Set" if asr_key else "Not set", bool(asr_key), "Required for ASR functionality"))
    
    llm_key = settings.llm_api_key
    checks.append(("LLM API Key", "Set" if llm_key else "Not set", bool(llm_key), "Required for text correction"))
    
    # Check port availability
    import socket
    port_ok = True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((settings.api_host, settings.api_port))
    except OSError:
        port_ok = False
    checks.append(("Port Availability", f"{settings.api_host}:{settings.api_port}", port_ok, "Port must be available"))
    
    # Display results
    table = Table(title="System Check Results")
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Notes", style="dim")
    
    all_passed = True
    for check_name, value, passed, notes in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        status_style = "green" if passed else "red"
        table.add_row(check_name, value, f"[{status_style}]{status}[/{status_style}]", notes)
        if not passed:
            all_passed = False
    
    console.print(table)
    
    if all_passed:
        console.print("\n🎉 All checks passed! Service is ready to start.", style="bold green")
    else:
        console.print("\n⚠️  Some checks failed. Please fix the issues before starting the service.", style="bold red")
        sys.exit(1)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Force initialization, overwrite existing files"),
):
    """Initialize a new ASR API Service project."""
    console.print("🚀 Initializing ASR API Service project", style="bold blue")
    
    # Create .env file
    env_file = Path(".env")
    if env_file.exists() and not force:
        console.print(f"❌ {env_file} already exists. Use --force to overwrite.", style="red")
        return
    
    env_content = """# ASR API Service Configuration

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_DEBUG=false
API_RELOAD=false

# ASR Configuration
ASR_PROVIDER=fireworks
WHISPER_API_KEY=your_whisper_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
FIREWORKS_API_KEY=your_fireworks_api_key_here

# LLM Configuration
LLM_PROVIDER=fireworks
LLM_API_KEY=your_llm_api_key_here
LLM_MODEL=accounts/fireworks/models/kimi-k2-instruct

# VAD Configuration
VAD_THRESHOLD=0.5
VAD_SILENCE_DURATION=0.8

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHUNK_DURATION=3.0
AUDIO_LOOKBACK_DURATION=9.0

# Storage Configuration
AUDIO_STORAGE_PATH=./data/audio
LOG_STORAGE_PATH=./data/logs
TEMP_STORAGE_PATH=./data/temp

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json

# Security Configuration
SECRET_KEY=change-this-in-production-use-a-long-random-string
"""
    
    with open(env_file, "w") as f:
        f.write(env_content)
    
    console.print(f"✅ Created {env_file}", style="green")
    
    # Create data directories
    for dir_name in ["data/audio", "data/logs", "data/temp"]:
        dir_path = Path(dir_name)
        dir_path.mkdir(parents=True, exist_ok=True)
        console.print(f"✅ Created directory {dir_path}", style="green")
    
    console.print("\n🎉 Project initialized successfully!", style="bold green")
    console.print("📝 Edit the .env file to configure your API keys and settings.", style="yellow")
    console.print("🚀 Run 'asr-api serve' to start the service.", style="blue")


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()