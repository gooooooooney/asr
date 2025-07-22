#!/usr/bin/env python3
"""Example streaming ASR client."""

import asyncio
import json
import time
from typing import List

import websockets
import numpy as np


class StreamingASRClient:
    """Example streaming ASR client."""
    
    def __init__(self, server_url: str = "ws://localhost:8000/api/v1/stream"):
        self.server_url = server_url
        self.websocket = None
        self.is_connected = False
        
    async def connect(self, api_key: str, enable_llm: bool = False):
        """Connect to the streaming ASR server."""
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.is_connected = True
            print(f"✅ Connected to {self.server_url}")
            
            # Send configuration
            config_message = {
                "type": "config",
                "data": {
                    "api_key": api_key,
                    "enable_llm": enable_llm,
                    "language": "en"
                },
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket.send(json.dumps(config_message))
            print("📝 Configuration sent")
            
            # Wait for ready status
            response = await self.websocket.recv()
            message = json.loads(response)
            
            if message["type"] == "status" and message["data"]["status"] == "ready":
                print("🚀 Server is ready")
                return True
            else:
                print(f"❌ Unexpected response: {message}")
                return False
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.websocket and self.is_connected:
            await self.websocket.close()
            self.is_connected = False
            print("👋 Disconnected")
    
    async def start_recording(self):
        """Start recording."""
        control_message = {
            "type": "control",
            "data": {
                "command": "start"
            },
            "timestamp": int(time.time() * 1000)
        }
        
        await self.websocket.send(json.dumps(control_message))
        print("🎤 Recording started")
    
    async def stop_recording(self):
        """Stop recording."""
        control_message = {
            "type": "control",
            "data": {
                "command": "stop"
            },
            "timestamp": int(time.time() * 1000)
        }
        
        await self.websocket.send(json.dumps(control_message))
        print("⏹️  Recording stopped")
    
    async def send_audio(self, audio_data: List[float], sample_rate: int = 16000):
        """Send audio data."""
        if not self.is_connected or not self.websocket:
            print("❌ Not connected to server")
            return
        
        audio_message = {
            "type": "audio",
            "data": {
                "audio_data": audio_data,
                "sample_rate": sample_rate
            },
            "timestamp": int(time.time() * 1000)
        }
        
        await self.websocket.send(json.dumps(audio_message))
    
    async def listen_for_results(self):
        """Listen for transcription results."""
        try:
            while self.is_connected:
                response = await self.websocket.recv()
                message = json.loads(response)
                
                if message["type"] == "result":
                    data = message["data"]
                    text = data.get("text", "")
                    corrected_text = data.get("corrected_text")
                    is_final = data.get("is_final", False)
                    is_reprocessed = data.get("is_reprocessed", False)
                    
                    status_icon = "✅" if is_final else "⏳"
                    reprocess_icon = "🔄" if is_reprocessed else ""
                    
                    display_text = corrected_text if corrected_text else text
                    print(f"{status_icon}{reprocess_icon} {display_text}")
                    
                elif message["type"] == "status":
                    data = message["data"]
                    if "vad_state" in data:
                        vad_state = data["vad_state"]
                        if vad_state.get("state_changed"):
                            state = vad_state.get("current_state")
                            if state == "speech":
                                print("🔊 Speech detected")
                            else:
                                print("🔇 Silence detected")
                                
                elif message["type"] == "error":
                    print(f"❌ Error: {message['data']['error']}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connection closed")
            self.is_connected = False
        except Exception as e:
            print(f"❌ Error listening for results: {e}")


def generate_test_audio(duration: float = 2.0, sample_rate: int = 16000, frequency: float = 440.0) -> List[float]:
    """Generate test audio signal (sine wave)."""
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, endpoint=False)
    
    # Generate a sine wave with some noise
    audio = 0.3 * np.sin(2 * np.pi * frequency * t)
    
    # Add some noise to make it more realistic
    noise = 0.05 * np.random.normal(0, 1, samples)
    audio = audio + noise
    
    # Clip to valid range
    audio = np.clip(audio, -1.0, 1.0)
    
    return audio.tolist()


async def main():
    """Main example function."""
    print("🎯 ASR Streaming Client Example")
    print("=" * 40)
    
    # Configuration
    API_KEY = input("Enter your API key: ").strip()
    if not API_KEY:
        print("❌ API key is required")
        return
    
    ENABLE_LLM = input("Enable LLM correction? (y/n): ").strip().lower() == 'y'
    
    # Create client
    client = StreamingASRClient()
    
    try:
        # Connect
        if not await client.connect(API_KEY, ENABLE_LLM):
            return
        
        # Start listening for results in background
        results_task = asyncio.create_task(client.listen_for_results())
        
        # Start recording
        await client.start_recording()
        
        # Simulate streaming audio
        print("\n🎵 Sending test audio...")
        
        # Generate and send audio in chunks
        chunk_duration = 0.5  # 500ms chunks
        total_duration = 5.0  # 5 seconds total
        
        for i in range(int(total_duration / chunk_duration)):
            # Generate audio chunk
            audio_chunk = generate_test_audio(
                duration=chunk_duration,
                frequency=440.0 + i * 50  # Vary frequency
            )
            
            await client.send_audio(audio_chunk)
            print(f"📤 Sent chunk {i+1}")
            
            # Wait between chunks
            await asyncio.sleep(chunk_duration * 0.8)  # Slight overlap
        
        # Wait a bit for final processing
        await asyncio.sleep(2.0)
        
        # Stop recording
        await client.stop_recording()
        
        # Wait for final results
        await asyncio.sleep(1.0)
        
        # Cancel results task
        results_task.cancel()
        
        print("\n✨ Example completed!")
        
    except KeyboardInterrupt:
        print("\n⏸️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    # Install required packages:
    # pip install websockets numpy
    
    try:
        import websockets
        import numpy as np
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Install with: pip install websockets numpy")
        exit(1)
    
    asyncio.run(main())