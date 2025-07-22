"""Streaming session manager."""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from uuid import uuid4

from fastapi import WebSocket
import structlog

from asr_api_service.config import settings
from asr_api_service.core.streaming.processor import StreamingProcessor
from asr_api_service.exceptions import StreamingError
from asr_api_service.models.streaming import (
    StreamingMessage,
    StreamingConfig,
    StreamingStatus,
    StreamingError as StreamingErrorModel,
)

logger = structlog.get_logger(__name__)


class StreamingClient:
    """Represents a streaming client session."""
    
    def __init__(self, client_id: str, websocket: WebSocket):
        self.client_id = client_id
        self.websocket = websocket
        self.processor: Optional[StreamingProcessor] = None
        self.connected_at = time.time()
        self.last_activity = time.time()
        self.total_messages = 0
        self.current_status = "connecting"
        self.remote_address = websocket.client.host if websocket.client else None
        
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
        self.total_messages += 1
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert client info to dictionary."""
        return {
            "client_id": self.client_id,
            "connected_at": self.connected_at,
            "last_activity": self.last_activity,
            "total_messages": self.total_messages,
            "current_status": self.current_status,
            "remote_address": self.remote_address,
        }


class StreamingManager:
    """Manages streaming ASR sessions and client connections."""
    
    def __init__(self):
        self.clients: Dict[str, StreamingClient] = {}
        self.start_time = time.time()
        self.total_connections = 0
        self.total_messages_processed = 0
        self.total_transcription_time_ms = 0
        self._lock = asyncio.Lock()
        
    async def add_client(self, websocket: WebSocket) -> str:
        """Add a new streaming client.
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            Client ID
            
        Raises:
            StreamingError: If maximum clients exceeded
        """
        async with self._lock:
            # Check client limit
            if len(self.clients) >= settings.streaming_max_clients:
                raise StreamingError(
                    f"Maximum clients ({settings.streaming_max_clients}) exceeded"
                )
            
            # Generate unique client ID
            client_id = str(uuid4())
            
            # Create client
            client = StreamingClient(client_id, websocket)
            self.clients[client_id] = client
            
            self.total_connections += 1
            
            logger.info(
                "Client added",
                client_id=client_id,
                total_clients=len(self.clients),
                remote_address=client.remote_address,
            )
            
            return client_id
    
    async def remove_client(self, client_id: str) -> None:
        """Remove a streaming client.
        
        Args:
            client_id: Client identifier
        """
        async with self._lock:
            client = self.clients.pop(client_id, None)
            if client:
                # Clean up processor
                if client.processor:
                    await client.processor.cleanup()
                
                logger.info(
                    "Client removed",
                    client_id=client_id,
                    session_duration=time.time() - client.connected_at,
                    total_messages=client.total_messages,
                )
    
    async def process_message(self, client_id: str, message: StreamingMessage) -> None:
        """Process a message from a streaming client.
        
        Args:
            client_id: Client identifier
            message: Streaming message to process
            
        Raises:
            StreamingError: If client not found or processing fails
        """
        client = self.clients.get(client_id)
        if not client:
            raise StreamingError(f"Client {client_id} not found")
        
        client.update_activity()
        self.total_messages_processed += 1
        
        try:
            if message.type == "config":
                await self._handle_config_message(client, message)
            elif message.type == "audio":
                await self._handle_audio_message(client, message)
            elif message.type == "control":
                await self._handle_control_message(client, message)
            else:
                logger.warning(
                    "Unknown message type",
                    client_id=client_id,
                    message_type=message.type,
                )
                await self.send_error(
                    client_id,
                    f"Unknown message type: {message.type}",
                    "UNKNOWN_MESSAGE_TYPE"
                )
                
        except Exception as e:
            logger.error(
                "Error processing message",
                client_id=client_id,
                message_type=message.type,
                error=str(e),
            )
            await self.send_error(
                client_id,
                f"Message processing error: {str(e)}",
                "MESSAGE_PROCESSING_ERROR"
            )
    
    async def _handle_config_message(self, client: StreamingClient, message: StreamingMessage) -> None:
        """Handle configuration message."""
        try:
            config = message.data
            if isinstance(config, dict):
                config = StreamingConfig(**config)
            
            logger.info(
                "Configuring client",
                client_id=client.client_id,
                enable_llm=config.enable_llm,
                language=config.language,
            )
            
            # Create or update processor
            if client.processor:
                await client.processor.cleanup()
            
            client.processor = StreamingProcessor(
                client_id=client.client_id,
                config=config,
                websocket=client.websocket,
            )
            
            # Initialize processor
            await client.processor.initialize()
            
            client.current_status = "ready"
            
            # Send ready status
            await self.send_status(client.client_id, "ready")
            
        except Exception as e:
            logger.error(
                "Configuration error",
                client_id=client.client_id,
                error=str(e),
            )
            client.current_status = "error"
            await self.send_error(
                client.client_id,
                f"Configuration error: {str(e)}",
                "CONFIGURATION_ERROR"
            )
    
    async def _handle_audio_message(self, client: StreamingClient, message: StreamingMessage) -> None:
        """Handle audio data message."""
        if not client.processor:
            await self.send_error(
                client.client_id,
                "Client not configured. Send config message first.",
                "CLIENT_NOT_CONFIGURED"
            )
            return
        
        try:
            client.current_status = "processing"
            processing_time = await client.processor.process_audio(message.data)
            
            if processing_time:
                self.total_transcription_time_ms += processing_time
            
        except Exception as e:
            logger.error(
                "Audio processing error",
                client_id=client.client_id,
                error=str(e),
            )
            client.current_status = "error"
            await self.send_error(
                client.client_id,
                f"Audio processing error: {str(e)}",
                "AUDIO_PROCESSING_ERROR"
            )
    
    async def _handle_control_message(self, client: StreamingClient, message: StreamingMessage) -> None:
        """Handle control message."""
        if not client.processor:
            await self.send_error(
                client.client_id,
                "Client not configured. Send config message first.",
                "CLIENT_NOT_CONFIGURED"
            )
            return
        
        try:
            await client.processor.handle_control(message.data)
            
        except Exception as e:
            logger.error(
                "Control processing error",
                client_id=client.client_id,
                error=str(e),
            )
            await self.send_error(
                client.client_id,
                f"Control processing error: {str(e)}",
                "CONTROL_PROCESSING_ERROR"
            )
    
    async def send_message(self, client_id: str, message: StreamingMessage) -> bool:
        """Send a message to a specific client.
        
        Args:
            client_id: Target client ID
            message: Message to send
            
        Returns:
            True if message was sent successfully
        """
        client = self.clients.get(client_id)
        if not client:
            logger.warning("Attempted to send message to non-existent client", client_id=client_id)
            return False
        
        try:
            message_json = message.model_dump_json()
            await client.websocket.send_text(message_json)
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send message",
                client_id=client_id,
                error=str(e),
            )
            # Remove client on send failure
            await self.remove_client(client_id)
            return False
    
    async def send_status(
        self, 
        client_id: str, 
        status: str, 
        vad_state: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """Send status message to client."""
        status_data = StreamingStatus(
            status=status,
            vad_state=vad_state,
            client_id=client_id,
            metadata=kwargs,
        )
        
        message = StreamingMessage.create_status(status_data)
        return await self.send_message(client_id, message)
    
    async def send_error(self, client_id: str, error_message: str, error_code: str) -> bool:
        """Send error message to client."""
        error_data = StreamingErrorModel(
            error=error_message,
            error_code=error_code,
            recoverable=error_code not in ["CONFIGURATION_ERROR", "CLIENT_NOT_CONFIGURED"],
        )
        
        message = StreamingMessage.create_error(error_data)
        return await self.send_message(client_id, message)
    
    async def send_control_command(self, client_id: str, command: Dict[str, Any]) -> bool:
        """Send control command to a specific client.
        
        Args:
            client_id: Target client ID
            command: Control command
            
        Returns:
            True if command was sent successfully
        """
        client = self.clients.get(client_id)
        if not client or not client.processor:
            return False
        
        try:
            await client.processor.handle_control(command)
            return True
        except Exception as e:
            logger.error(
                "Failed to send control command",
                client_id=client_id,
                command=command,
                error=str(e),
            )
            return False
    
    async def get_active_clients(self) -> List[Dict[str, Any]]:
        """Get list of active clients."""
        return [client.to_dict() for client in self.clients.values()]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get streaming manager statistics."""
        uptime = time.time() - self.start_time
        
        avg_processing_time = 0
        if self.total_messages_processed > 0:
            avg_processing_time = self.total_transcription_time_ms / self.total_messages_processed
        
        return {
            "active_clients": len(self.clients),
            "total_connections": self.total_connections,
            "total_messages_processed": self.total_messages_processed,
            "total_transcription_time_ms": self.total_transcription_time_ms,
            "average_processing_time_ms": avg_processing_time,
            "uptime_seconds": uptime,
            "max_concurrent_clients": settings.streaming_max_clients,
        }
    
    async def cleanup(self) -> None:
        """Clean up all clients and resources."""
        async with self._lock:
            for client_id in list(self.clients.keys()):
                await self.remove_client(client_id)
        
        logger.info("Streaming manager cleanup completed")