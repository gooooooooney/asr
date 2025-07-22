# ASR API Service Architecture

## Overview

The ASR API Service is a modern, production-ready speech recognition service built with FastAPI. It provides both REST API endpoints for batch transcription and WebSocket-based streaming for real-time speech recognition with Voice Activity Detection (VAD).

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Client Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  Web Clients  │  Mobile Apps  │  Python Scripts  │  cURL/Postman │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway                              │
├─────────────────────────────────────────────────────────────────┤
│                 FastAPI Application                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ REST API    │  │ WebSocket   │  │ Health      │              │
│  │ /api/v1/    │  │ /stream     │  │ /health     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Business Logic                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Audio        │  │ ASR         │  │ Streaming   │             │
│  │ Processing   │  │ Providers   │  │ Manager     │             │
│  └──────────────┘  └─────────────┘  └─────────────┘             │
│  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ VAD          │  │ LLM         │  │ Session     │             │
│  │ Processing   │  │ Correction  │  │ Management  │             │
│  └──────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ OpenAI      │  │ Fireworks   │  │ Anthropic   │              │
│  │ Whisper API │  │ AI API      │  │ Claude API  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Storage Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Audio Files │  │ Logs        │  │ Temp Files  │              │
│  │ Storage     │  │ Storage     │  │ Storage     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (`src/asr_api_service/api/`)

**REST API Endpoints:**
- `POST /api/v1/transcribe` - Batch audio transcription
- `POST /api/v1/transcribe-raw` - Raw audio data transcription
- `GET /api/v1/models` - List available models
- `GET /api/v1/test-connection` - Test ASR provider connection

**WebSocket Endpoints:**
- `WS /api/v1/stream` - Real-time streaming transcription
- `GET /api/v1/streaming-stats` - Streaming service statistics

**Health & Monitoring:**
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health check with system status
- `GET /ready` - Kubernetes readiness probe
- `GET /live` - Kubernetes liveness probe

### 2. Audio Processing (`src/asr_api_service/core/audio/`)

**AudioBuffer (`buffer.py`)**
- Manages streaming audio data with circular buffer
- Supports chunking, segmentation, and audio metrics
- Thread-safe operations with proper memory management

**VAD Processor (`vad.py`)**
- Voice Activity Detection using TEN-VAD
- Falls back to energy-based VAD if TEN-VAD unavailable  
- Real-time speech/silence classification
- Configurable thresholds and silence duration

**Key Features:**
- Real-time audio buffering with configurable chunk sizes
- Advanced VAD with speech state tracking
- Audio validation and normalization
- RMS and peak level monitoring

### 3. ASR Providers (`src/asr_api_service/core/asr/`)

**Base ASR Provider (`base.py`)**
- Abstract interface for ASR services
- Standardized result format
- Audio validation and preprocessing utilities

**Whisper ASR Provider (`whisper.py`)**
- OpenAI Whisper API integration
- Fireworks AI API support
- Configurable models and parameters
- Robust error handling and retries

**Provider Features:**
- Multiple ASR backend support (OpenAI, Fireworks)
- Context-aware transcription with prompts
- Language detection and specification
- Processing time tracking

### 4. Streaming Engine (`src/asr_api_service/core/streaming/`)

**Streaming Manager (`manager.py`)**
- WebSocket connection management
- Client session tracking
- Message routing and protocol handling
- Resource cleanup and monitoring

**Streaming Processor (`processor.py`)**
- Real-time audio processing pipeline
- VAD-based segment detection
- Adaptive chunking and reprocessing
- Context-aware transcription

**Streaming Features:**
- Real-time speech recognition with VAD
- Intelligent segment reprocessing for accuracy
- Configurable chunk duration and lookback
- Client session management and cleanup

### 5. Configuration Management (`src/asr_api_service/config.py`)

**Environment-based Configuration:**
- Pydantic Settings for validation
- Type-safe configuration with defaults
- API key management per provider
- Audio and VAD parameter tuning

**Configuration Categories:**
- API settings (host, port, workers, CORS)
- ASR provider configuration (keys, URLs, models)
- Audio processing parameters (sample rate, chunk duration)
- VAD settings (threshold, silence duration)
- Streaming configuration (max clients, timeouts)
- Logging and monitoring settings

## Data Flow

### REST API Flow

```
Audio File Upload → Validation → Format Conversion → ASR Provider → 
LLM Correction (optional) → Response Formatting → JSON Response
```

### Streaming Flow

```
WebSocket Connect → Client Registration → Configuration → 
Audio Stream → VAD Processing → Segment Detection → 
ASR Processing → LLM Correction → Result Broadcasting → 
Session Cleanup
```

### VAD-based Segmentation

```
Audio Chunks → VAD Analysis → State Detection (speech/silence) →
Timeout-based Chunking → Speech End Detection → 
Segment Reprocessing → Final Results
```

## Key Algorithms

### 1. VAD-based Segmentation

The service uses a sophisticated segmentation algorithm:

1. **Real-time VAD**: Process incoming audio with TEN-VAD
2. **State Tracking**: Monitor speech start/end with hysteresis
3. **Timeout Chunking**: Process long speech in ~3s chunks
4. **Lookback Reprocessing**: Reprocess up to 9s for accuracy
5. **Adaptive Context**: Use previous results as prompt context

### 2. Intelligent Reprocessing

When speech ends, the system decides whether to:
- Reprocess entire segment (≤9s duration)
- Reprocess from lookback boundary (>9s duration)  
- Process only final segment (no previous chunks)

This ensures optimal accuracy while managing computational costs.

### 3. Session Management

- **Client Lifecycle**: Connect → Configure → Process → Cleanup
- **Resource Tracking**: Monitor memory, connections, processing time
- **Graceful Shutdown**: Handle disconnections and cleanup resources
- **Rate Limiting**: Prevent resource exhaustion

## Error Handling

### Structured Error Types

- `ASRServiceError`: Base exception with error codes
- `AudioProcessingError`: Audio validation and processing issues
- `ASRProviderError`: External API failures with retry logic
- `StreamingError`: WebSocket and session management errors
- `VADError`: Voice activity detection issues

### Resilience Patterns

- **Circuit Breaker**: Prevent cascade failures to external APIs
- **Retry Logic**: Exponential backoff for transient failures
- **Graceful Degradation**: Fallback to simple VAD if TEN-VAD fails
- **Resource Limits**: Prevent memory leaks and resource exhaustion

## Performance Considerations

### Scalability

- **Horizontal Scaling**: Multiple worker processes
- **Session Isolation**: Independent client processing
- **Memory Management**: Bounded audio buffers
- **Async Processing**: Non-blocking I/O operations

### Optimization Strategies

- **Chunked Processing**: Process long audio incrementally
- **Context Reuse**: Leverage conversation history
- **Buffer Management**: Automatic cleanup of old data
- **Connection Pooling**: Reuse HTTP connections to providers

## Security

### Authentication & Authorization

- API key-based authentication
- JWT token support (placeholder for future)
- Rate limiting per client
- Input validation and sanitization

### Data Protection

- Audio data is not persisted by default
- Temporary files are automatically cleaned up
- Configurable data retention policies
- Optional encryption at rest

## Deployment

### Docker Support

- Multi-stage Dockerfile for optimized images
- Docker Compose for development
- Health check integration
- Non-root user execution

### Kubernetes Ready

- Liveness and readiness probes
- Configurable resource limits
- Horizontal pod autoscaling support
- Graceful shutdown handling

### Monitoring

- Prometheus metrics endpoint
- Structured JSON logging
- Health check endpoints
- Performance monitoring

## Development Workflow

### Code Quality

- **Type Safety**: Full type hints with mypy
- **Testing**: Pytest with async support
- **Linting**: flake8, black, isort
- **Pre-commit Hooks**: Automated quality checks

### Project Structure

```
asr_api_service/
├── src/asr_api_service/           # Main package
│   ├── api/                       # FastAPI routes
│   ├── core/                      # Business logic
│   ├── models/                    # Pydantic models
│   ├── utils/                     # Utilities
│   └── config.py                  # Configuration
├── tests/                         # Test suite
├── examples/                      # Usage examples
├── docker/                        # Docker configs
└── docs/                          # Documentation
```

## Future Enhancements

### Planned Features

1. **Additional ASR Providers**: Azure, Google Cloud, AWS
2. **LLM Integration**: Full text correction pipeline
3. **Batch Processing**: Job queue for large files
4. **Speaker Diarization**: Multi-speaker support
5. **Custom Models**: Fine-tuned model support
6. **Caching Layer**: Redis for frequent requests
7. **Database Integration**: PostgreSQL for persistence
8. **Advanced Analytics**: Usage metrics and insights

### Performance Improvements

1. **GPU Acceleration**: CUDA support for VAD/ASR
2. **Model Optimization**: ONNX runtime integration  
3. **Connection Pooling**: Persistent connections
4. **Caching**: Intelligent result caching
5. **Load Balancing**: Advanced routing strategies

This architecture provides a solid foundation for production speech recognition services while maintaining flexibility for future enhancements and scaling requirements.