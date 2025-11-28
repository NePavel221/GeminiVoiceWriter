"""Gemini Live API transcriber for real-time audio streaming."""
import asyncio
import base64
import threading
import queue
from typing import Optional, Callable

from google import genai
from google.genai import types


class LiveTranscriber:
    """
    Real-time transcriber using Gemini Live API.
    Streams audio during recording for instant transcription.
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-live-001"):
        self.api_key = api_key
        self.model = model
        self.client: Optional[genai.Client] = None
        self.session = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._is_streaming = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._transcription_result = ""
        self._on_transcription: Optional[Callable[[str], None]] = None
        
    def start_session(self, on_transcription: Optional[Callable[[str], None]] = None):
        """Start a new live session for streaming audio."""
        self._on_transcription = on_transcription
        self._transcription_result = ""
        self._is_streaming = True
        
        # Run async session in separate thread
        self._thread = threading.Thread(target=self._run_async_session, daemon=True)
        self._thread.start()
    
    def _run_async_session(self):
        """Run the async session in a separate thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_session())
        except Exception as e:
            print(f"LiveTranscriber session error: {e}")
        finally:
            self._loop.close()
    
    async def _async_session(self):
        """Async session that handles streaming."""
        try:
            # Create client
            self.client = genai.Client(api_key=self.api_key)
            
            # Configure for audio input, text output
            config = types.LiveConnectConfig(
                response_modalities=["TEXT"],
                speech_config=types.SpeechConfig(
                    voice_config=None  # We only want transcription, not TTS
                )
            )
            
            async with self.client.aio.live.connect(
                model=self.model,
                config=config
            ) as session:
                self.session = session
                
                # Send system instruction
                await session.send_client_content(
                    turns=[{
                        "role": "user",
                        "parts": [{"text": "You are a transcription assistant. Listen to the audio and transcribe exactly what is spoken. Return ONLY the transcribed text, nothing else."}]
                    }],
                    turn_complete=True
                )
                
                # Start tasks for sending audio and receiving responses
                send_task = asyncio.create_task(self._send_audio_chunks())
                receive_task = asyncio.create_task(self._receive_responses())
                
                # Wait for streaming to stop
                while self._is_streaming:
                    await asyncio.sleep(0.1)
                
                # Signal end of audio
                await session.send_realtime_input(
                    audio=types.Blob(data=b"", mime_type="audio/pcm;rate=16000"),
                    end_of_turn=True
                )
                
                # Wait a bit for final response
                await asyncio.sleep(0.5)
                
                # Cancel tasks
                send_task.cancel()
                receive_task.cancel()
                
        except Exception as e:
            print(f"LiveTranscriber async error: {e}")
            import traceback
            traceback.print_exc()
    
    async def _send_audio_chunks(self):
        """Send audio chunks from queue to the session."""
        try:
            while self._is_streaming or not self._audio_queue.empty():
                try:
                    # Non-blocking get with timeout
                    chunk = self._audio_queue.get(timeout=0.1)
                    if chunk and self.session:
                        # Send as PCM audio
                        await self.session.send_realtime_input(
                            audio=types.Blob(
                                data=chunk,
                                mime_type="audio/pcm;rate=16000"
                            )
                        )
                except queue.Empty:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Send audio error: {e}")
    
    async def _receive_responses(self):
        """Receive transcription responses from the session."""
        try:
            while self._is_streaming:
                if self.session:
                    async for response in self.session.receive():
                        if response.text:
                            self._transcription_result += response.text
                            if self._on_transcription:
                                self._on_transcription(response.text)
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Receive response error: {e}")
    
    def send_audio_chunk(self, chunk: bytes):
        """Send an audio chunk to be transcribed. Call this during recording."""
        if self._is_streaming:
            self._audio_queue.put(chunk)
    
    def stop_session(self) -> str:
        """Stop the session and return the transcription."""
        self._is_streaming = False
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        return self._transcription_result
    
    def get_transcription(self) -> str:
        """Get current transcription result."""
        return self._transcription_result


class SimpleLiveTranscriber:
    """
    Simplified Live API transcriber - collects audio, sends at end.
    More reliable than full streaming but still uses Live API.
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-live-001"):
        self.api_key = api_key
        self.model = model
        self._audio_chunks: list[bytes] = []
        self._is_recording = False
    
    def start_recording(self):
        """Start collecting audio chunks."""
        self._audio_chunks = []
        self._is_recording = True
    
    def add_chunk(self, chunk: bytes):
        """Add an audio chunk."""
        if self._is_recording:
            self._audio_chunks.append(chunk)
    
    async def transcribe_async(self) -> str:
        """Transcribe collected audio using Live API."""
        if not self._audio_chunks:
            return ""
        
        try:
            client = genai.Client(api_key=self.api_key)
            
            config = types.LiveConnectConfig(
                response_modalities=["TEXT"]
            )
            
            result = ""
            
            async with client.aio.live.connect(
                model=self.model,
                config=config
            ) as session:
                # Send all audio at once
                audio_data = b''.join(self._audio_chunks)
                
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=audio_data,
                        mime_type="audio/pcm;rate=16000"
                    ),
                    end_of_turn=True
                )
                
                # Receive response
                async for response in session.receive():
                    if response.text:
                        result += response.text
                    if response.server_content and response.server_content.turn_complete:
                        break
            
            return result
            
        except Exception as e:
            print(f"SimpleLiveTranscriber error: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def transcribe(self) -> str:
        """Synchronous wrapper for transcribe_async."""
        self._is_recording = False
        return asyncio.run(self.transcribe_async())
