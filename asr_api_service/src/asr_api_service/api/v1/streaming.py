"""Streaming ASR WebSocket endpoint."""

import json
import time
from typing import Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

from asr_api_service.config import settings
from asr_api_service.models.streaming import StreamingMessage
from asr_api_service.core.streaming.manager import StreamingManager

router = APIRouter()
logger = structlog.get_logger(__name__)

# Global streaming manager instance
streaming_manager = StreamingManager()


@router.websocket("/stream")
async def streaming_websocket(websocket: WebSocket):
    """WebSocket endpoint for streaming ASR.
    
    This endpoint handles real-time audio streaming and provides
    continuous transcription results with VAD-based segmentation.
    
    Protocol:
    - Client connects and sends configuration
    - Client streams audio data
    - Server responds with transcription results and status updates
    - Client can send control commands (start, stop, reset)
    """
    client_id = None
    
    try:
        # Accept WebSocket connection
        await websocket.accept()
        
        # Register client with streaming manager
        client_id = await streaming_manager.add_client(websocket)
        
        logger.info(
            "Streaming client connected",
            client_id=client_id,
            remote_address=websocket.client.host if websocket.client else None,
        )
        
        # Set WebSocket options for better performance
        # Note: These may not be directly available in FastAPI WebSockets
        # but are handled by the underlying implementation
        
        # Main message loop
        while True:
            try:
                # Receive message from client
                raw_message = await websocket.receive_text()
                
                # Parse message
                try:
                    message_data = json.loads(raw_message)
                    message = StreamingMessage(**message_data)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "Invalid message format",
                        client_id=client_id,
                        error=str(e),
                        raw_message=raw_message[:200],  # Log first 200 chars
                    )
                    await streaming_manager.send_error(
                        client_id,
                        f"Invalid message format: {str(e)}",
                        "INVALID_MESSAGE_FORMAT"
                    )
                    continue
                
                # Process message
                await streaming_manager.process_message(client_id, message)
                
            except WebSocketDisconnect:
                logger.info("Client disconnected normally", client_id=client_id)
                break
            
            except Exception as e:
                logger.error(
                    "Error processing message",
                    client_id=client_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                
                # Send error to client
                await streaming_manager.send_error(
                    client_id,
                    f"Message processing error: {str(e)}",
                    "MESSAGE_PROCESSING_ERROR"
                )
    
    except WebSocketDisconnect:
        logger.info("Client disconnected during handshake")
    
    except Exception as e:
        logger.exception(
            "Streaming WebSocket error",
            client_id=client_id,
            error=str(e),
        )
    
    finally:
        # Clean up client
        if client_id:
            await streaming_manager.remove_client(client_id)
            logger.info("Client cleaned up", client_id=client_id)


@router.get("/streaming-stats")
async def get_streaming_stats():
    """Get streaming service statistics."""
    stats = await streaming_manager.get_stats()
    
    return {
        "active_clients": stats.get("active_clients", 0),
        "total_connections": stats.get("total_connections", 0),
        "total_messages_processed": stats.get("total_messages_processed", 0),
        "total_transcription_time_ms": stats.get("total_transcription_time_ms", 0),
        "average_processing_time_ms": stats.get("average_processing_time_ms", 0),
        "uptime_seconds": stats.get("uptime_seconds", 0),
        "max_concurrent_clients": settings.streaming_max_clients,
        "vad_settings": {
            "threshold": settings.vad_threshold,
            "silence_duration": settings.vad_silence_duration,
            "hop_size": settings.vad_hop_size,
        },
        "audio_settings": {
            "sample_rate": settings.audio_sample_rate,
            "chunk_duration": settings.audio_chunk_duration,
            "lookback_duration": settings.audio_lookback_duration,
        },
    }


@router.post("/streaming-control/{client_id}")
async def streaming_control(client_id: str, command: Dict[str, Any]):
    """Send control commands to a specific streaming client.
    
    This endpoint allows external systems to control streaming sessions.
    Useful for administrative operations or integration with other services.
    """
    try:
        success = await streaming_manager.send_control_command(client_id, command)
        
        if success:
            return {"success": True, "message": f"Command sent to client {client_id}"}
        else:
            return {"success": False, "message": f"Client {client_id} not found"}
    
    except Exception as e:
        logger.error(
            "Failed to send control command",
            client_id=client_id,
            command=command,
            error=str(e),
        )
        return {"success": False, "message": f"Error: {str(e)}"}


@router.get("/active-clients")
async def get_active_clients():
    """Get list of active streaming clients."""
    clients = await streaming_manager.get_active_clients()
    
    return {
        "clients": [
            {
                "client_id": client["client_id"],
                "connected_at": client["connected_at"],
                "last_activity": client["last_activity"],
                "total_messages": client["total_messages"],
                "current_status": client["current_status"],
                "remote_address": client.get("remote_address"),
            }
            for client in clients
        ],
        "total_clients": len(clients),
    }


# Health check for streaming service
@router.get("/streaming-health")
async def streaming_health_check():
    """Health check specific to streaming functionality."""
    health_info = {
        "status": "healthy",
        "streaming_manager": "operational",
        "vad_available": True,  # This would check if TEN-VAD is loaded
        "asr_provider": settings.asr_provider,
        "max_clients": settings.streaming_max_clients,
    }
    
    # Check if ASR provider is configured
    if not settings.get_asr_api_key():
        health_info["status"] = "degraded"
        health_info["issues"] = ["ASR API key not configured"]
    
    # Check active clients
    stats = await streaming_manager.get_stats()
    active_clients = stats.get("active_clients", 0)
    
    if active_clients >= settings.streaming_max_clients:
        health_info["status"] = "at_capacity"
        health_info["active_clients"] = active_clients
    
    return health_info