"""Gemini Live API transcriber for real-time audio streaming with proxy support."""
import asyncio
import base64
import threading
import queue
import os
from typing import Optional, Callable
from urllib.parse import urlparse

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from utils.logger import get_logger

log = get_logger()


class LiveTranscriber:
    """
    Real-time transcriber using Gemini Live API.
    Streams audio during recording for instant transcription.
    Supports HTTP proxy for bypassing regional restrictions.
    """
    
    # Available Live API models
    MODELS = [
        "gemini-2.5-flash-native-audio-preview-09-2025",
        "gemini-2.0-flash-live-001", 
    ]
    
    def __init__(
        self, 
        api_key: str, 
        model: str = "gemini-2.5-flash-native-audio-preview-09-2025",
        proxy_url: Optional[str] = None,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        self.api_key = api_key
        self.model = model
        self.proxy_url = proxy_url
        self._on_transcription = on_transcription
        self._on_error = on_error
        
        self.client: Optional[genai.Client] = None
        self.session = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._is_streaming = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._transcription_result = ""
        self._partial_text = ""
        
        # Audio params (must match recorder)
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2  # 16-bit

    def start_session(self, on_transcription: Optional[Callable[[str], None]] = None):
        """Start a new live session for streaming audio."""
        if on_transcription:
            self._on_transcription = on_transcription
        self._transcription_result = ""
        self._partial_text = ""
        self._is_streaming = True
        self._audio_queue = queue.Queue()
        
        log.info(f"[LIVE] Starting session with model: {self.model}")
        if self.proxy_url:
            log.info(f"[LIVE] Using proxy: {self.proxy_url[:30]}...")
        
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
            log.error(f"[LIVE] Session error: {e}")
            if self._on_error:
                self._on_error(str(e))
        finally:
            self._loop.close()
    
    async def _async_session(self):
        """Async session that handles streaming."""
        try:
            # Configure proxy if provided
            http_options = None
            if self.proxy_url:
                # Set environment variable for httpx (used by google-genai)
                os.environ["HTTPS_PROXY"] = self.proxy_url
                os.environ["HTTP_PROXY"] = self.proxy_url
                log.info("[LIVE] Proxy environment variables set")
            
            # Create client
            self.client = genai.Client(api_key=self.api_key)
            
            # Configure for audio input with transcription
            config = {
                "response_modalities": ["TEXT"],
                "input_audio_transcription": {},  # Enable input transcription
            }
            
            log.info(f"[LIVE] Connecting to {self.model}...")
            
            async with self.client.aio.live.connect(
                model=self.model,
                config=config
            ) as session:
                self.session = session
                log.info("[LIVE] Connected successfully")
                
                # Start tasks for sending audio and receiving responses
                send_task = asyncio.create_task(self._send_audio_chunks())
                receive_task = asyncio.create_task(self._receive_responses())
                
                # Wait for streaming to stop
                while self._is_streaming:
                    await asyncio.sleep(0.1)
                
                log.info("[LIVE] Streaming stopped, sending end signal...")
                
                # Signal end of audio stream
                try:
                    await session.send_realtime_input(audio_stream_end=True)
                except Exception as e:
                    log.warning(f"[LIVE] Error sending stream end: {e}")
                
                # Wait for final responses
                await asyncio.sleep(1.0)
                
                # Cancel tasks
                send_task.cancel()
                receive_task.cancel()
                
                log.info(f"[LIVE] Session complete. Result: {len(self._transcription_result)} chars")
                
        except Exception as e:
            log.error(f"[LIVE] Async error: {e}")
            import traceback
            traceback.print_exc()
            if self._on_error:
                self._on_error(str(e))

    async def _send_audio_chunks(self):
        """Send audio chunks from queue to the session."""
        chunks_sent = 0
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
                        chunks_sent += 1
                        if chunks_sent % 50 == 0:
                            log.debug(f"[LIVE] Sent {chunks_sent} audio chunks")
                except queue.Empty:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            log.debug(f"[LIVE] Send task cancelled after {chunks_sent} chunks")
        except Exception as e:
            log.error(f"[LIVE] Send audio error: {e}")
    
    async def _receive_responses(self):
        """Receive transcription responses from the session."""
        try:
            if not self.session:
                return
                
            async for response in self.session.receive():
                # Check for input transcription (what user said)
                if hasattr(response, 'server_content') and response.server_content:
                    sc = response.server_content
                    
                    # Input transcription - this is what we want!
                    if hasattr(sc, 'input_transcription') and sc.input_transcription:
                        text = sc.input_transcription.text
                        if text:
                            self._transcription_result = text
                            self._partial_text = text
                            log.debug(f"[LIVE] Input transcription: {text[:50]}...")
                            if self._on_transcription:
                                self._on_transcription(text)
                    
                    # Model turn (response from model)
                    if hasattr(sc, 'model_turn') and sc.model_turn:
                        for part in sc.model_turn.parts or []:
                            if hasattr(part, 'text') and part.text:
                                # This is model's response, not transcription
                                log.debug(f"[LIVE] Model response: {part.text[:50]}...")
                    
                    # Turn complete
                    if hasattr(sc, 'turn_complete') and sc.turn_complete:
                        log.debug("[LIVE] Turn complete")
                
                # Direct text response
                if hasattr(response, 'text') and response.text:
                    self._transcription_result += response.text
                    if self._on_transcription:
                        self._on_transcription(response.text)
                        
        except asyncio.CancelledError:
            log.debug("[LIVE] Receive task cancelled")
        except Exception as e:
            log.error(f"[LIVE] Receive response error: {e}")
    
    def send_audio_chunk(self, chunk: bytes):
        """Send an audio chunk to be transcribed. Call this during recording."""
        if self._is_streaming:
            self._audio_queue.put(chunk)
    
    def stop_session(self) -> str:
        """Stop the session and return the transcription."""
        log.info("[LIVE] Stopping session...")
        self._is_streaming = False
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        
        # Clean up proxy env vars
        if self.proxy_url:
            os.environ.pop("HTTPS_PROXY", None)
            os.environ.pop("HTTP_PROXY", None)
        
        log.info(f"[LIVE] Session stopped. Result: {len(self._transcription_result)} chars")
        return self._transcription_result
    
    def get_transcription(self) -> str:
        """Get current transcription result."""
        return self._transcription_result
    
    def get_partial_text(self) -> str:
        """Get partial/intermediate transcription text."""
        return self._partial_text
    
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._is_streaming
