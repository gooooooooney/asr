# ASR API Service

A modern, production-ready ASR (Automatic Speech Recognition) API service built with FastAPI, featuring real-time streaming capabilities, Voice Activity Detection (VAD), and robust audio processing.

## Features

- **Real-time Streaming ASR**: WebSocket-based streaming speech recognition
- **Voice Activity Detection**: Advanced VAD using TEN-VAD for speech/silence detection
- **Multiple ASR Backends**: Support for Whisper API and other ASR services
- **Text Post-processing**: LLM-based text correction and enhancement
- **RESTful API**: Standard HTTP endpoints for batch processing
- **Modern Architecture**: Built with FastAPI, async/await, and type hints
- **Production Ready**: Comprehensive logging, monitoring, and error handling
- **Scalable**: Designed for horizontal scaling with load balancers
- **Configurable**: Environment-based configuration management

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/meetingcode/asr-api-service.git
cd asr-api-service

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

### Configuration

Create a `.env` file in the project root:

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# ASR Service Configuration
WHISPER_API_KEY=your_whisper_api_key
WHISPER_API_URL=https://api.openai.com/v1/audio/transcriptions
LLM_API_KEY=your_llm_api_key
LLM_API_URL=https://api.fireworks.ai/inference/v1/chat/completions

# VAD Configuration
VAD_THRESHOLD=0.5
VAD_SILENCE_DURATION=0.8
VAD_HOP_SIZE=256

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHUNK_DURATION=3.0
AUDIO_LOOKBACK_DURATION=9.0

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Storage
AUDIO_STORAGE_PATH=./data/audio
LOG_STORAGE_PATH=./data/logs
```

### Running the Service

```bash
# Development mode
asr-api serve --reload

# Production mode
asr-api serve --workers 4

# Using uvicorn directly
uvicorn asr_api_service.main:app --host 0.0.0.0 --port 8000
```

### API Usage

#### REST API Endpoints

```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# Upload audio file for transcription
with open("audio.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/transcribe",
        files={"audio": f},
        data={"enable_llm": True}
    )
print(response.json())
```

#### WebSocket Streaming

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/stream");

// Configure the connection
ws.onopen = () => {
    ws.send(JSON.stringify({
        type: "config",
        data: {
            apiKey: "your-api-key",
            enableLLM: true
        }
    }));
};

// Handle messages
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("Received:", data);
};

// Send audio data
ws.send(JSON.stringify({
    type: "audio",
    data: {
        audioData: audioArray
    }
}));
```

## Architecture

### Project Structure

```
asr_api_service/
├── src/asr_api_service/        # Main package
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── cli.py                  # Command-line interface
│   ├── config.py               # Configuration management
│   ├── api/                    # API routes and handlers
│   │   ├── __init__.py
│   │   ├── v1/                 # API v1
│   │   │   ├── __init__.py
│   │   │   ├── transcription.py
│   │   │   ├── streaming.py
│   │   │   └── health.py
│   │   └── middleware/         # Custom middleware
│   ├── core/                   # Core business logic
│   │   ├── __init__.py
│   │   ├── audio/              # Audio processing
│   │   │   ├── __init__.py
│   │   │   ├── buffer.py
│   │   │   ├── vad.py
│   │   │   └── preprocessing.py
│   │   ├── asr/                # ASR services
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── whisper.py
│   │   │   └── openai.py
│   │   ├── llm/                # LLM services
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── correction.py
│   │   └── streaming/          # Streaming logic
│   │       ├── __init__.py
│   │       ├── manager.py
│   │       └── processor.py
│   ├── models/                 # Pydantic models
│   │   ├── __init__.py
│   │   ├── audio.py
│   │   ├── transcription.py
│   │   └── streaming.py
│   ├── utils/                  # Utilities
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   ├── storage.py
│   │   └── validation.py
│   └── exceptions.py           # Custom exceptions
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                       # Documentation
├── docker/                     # Docker configurations
├── scripts/                    # Utility scripts
└── configs/                    # Configuration files
```

### Key Components

1. **Audio Processing Pipeline**:
   - Audio buffer management with configurable chunking
   - VAD-based speech activity detection
   - Real-time audio preprocessing and validation

2. **ASR Services**:
   - Pluggable ASR backend support (Whisper, OpenAI, etc.)
   - Streaming and batch transcription modes
   - Context-aware processing with conversation history

3. **LLM Post-processing**:
   - Text correction and enhancement
   - Grammar and punctuation improvement
   - Configurable correction strategies

4. **Streaming Engine**:
   - WebSocket-based real-time communication
   - Client session management
   - Adaptive chunk processing and reprocessing

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m e2e

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_audio_buffer.py
```

### Code Quality

The project uses several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Static type checking
- **pytest**: Testing framework
- **pre-commit**: Git hooks for quality checks

## Deployment

### Docker Deployment

```bash
# Build image
docker build -t asr-api-service .

# Run container
docker run -p 8000:8000 --env-file .env asr-api-service
```

### Docker Compose

```yaml
version: '3.8'
services:
  asr-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### Production Considerations

- Use environment variables for sensitive configuration
- Set up proper logging and monitoring
- Configure reverse proxy (nginx) for SSL termination
- Implement rate limiting and authentication
- Set up health checks and auto-scaling
- Monitor memory usage for audio processing

## API Reference

### REST Endpoints

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `POST /api/v1/transcribe` - Transcribe audio file
- `GET /api/v1/models` - List available models
- `WebSocket /api/v1/stream` - Real-time streaming

### WebSocket Protocol

The streaming API uses a message-based protocol:

```json
{
  "type": "config|audio|control",
  "data": { ... },
  "timestamp": 1234567890
}
```

See the [API documentation](docs/api.md) for detailed specifications.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.