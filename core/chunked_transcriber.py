"""Chunked REST API transcriber for fast parallel transcription."""
import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, List, Dict
import requests
import wave
import io

from utils.logger import get_logger

log = get_logger()


class ChunkedTranscriber:
    """
    Transcriber that sends audio chunks in parallel during recording.
    Achieves 3-5 second transcription time regardless of recording length.
    """
    
    CHUNK_DURATION = 10  # seconds
    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        proxy_url: Optional[str] = None,
        language: str = "Russian",
        on_chunk_result: Optional[Callable[[int, str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        self.api_key = api_key
        self.model = model
        self.proxy_url = proxy_url
        self.language = language
        self._on_chunk_result = on_chunk_result
        self._on_error = on_error
        
        # Audio buffer
        self._audio_buffer: List[bytes] = []
        self._buffer_lock = threading.Lock()
        
        # Results storage (chunk_index -> text)
        self._results: Dict[int, str] = {}
        self._results_lock = threading.Lock()
        
        # Chunk tracking
        self._chunk_index = 0
        self._is_active = False
        
        # Thread pool for parallel requests
        self._executor: Optional[ThreadPoolExecutor] = None
        self._pending_futures = []
        
        # Bytes per chunk (10 sec * 16000 Hz * 2 bytes * 1 channel)
        self._bytes_per_chunk = self.CHUNK_DURATION * self.SAMPLE_RATE * self.SAMPLE_WIDTH * self.CHANNELS
        
        log.info(f"[CHUNKED] Initialized: {self.CHUNK_DURATION}s chunks, model={model}")
    
    def start(self):
        """Start the chunked transcriber."""
        self._is_active = True
        self._audio_buffer = []
        self._results = {}
        self._chunk_index = 0
        self._pending_futures = []
        self._executor = ThreadPoolExecutor(max_workers=5)
        log.info("[CHUNKED] Started")
    
    def add_audio(self, chunk: bytes):
        """Add audio data. Automatically sends chunks when buffer is full."""
        if not self._is_active:
            return
        
        with self._buffer_lock:
            self._audio_buffer.append(chunk)
            
            # Calculate total bytes in buffer
            total_bytes = sum(len(c) for c in self._audio_buffer)
            
            # If we have enough for a chunk, send it
            if total_bytes >= self._bytes_per_chunk:
                self._send_chunk()
    
    def _send_chunk(self):
        """Extract chunk from buffer and send for transcription."""
        # Combine buffer into single bytes
        audio_data = b''.join(self._audio_buffer)
        
        # Extract chunk (first CHUNK_DURATION seconds)
        chunk_data = audio_data[:self._bytes_per_chunk]
        
        # Keep remainder in buffer
        remainder = audio_data[self._bytes_per_chunk:]
        self._audio_buffer = [remainder] if remainder else []
        
        # Send chunk asynchronously
        chunk_idx = self._chunk_index
        self._chunk_index += 1
        
        log.info(f"[CHUNKED] Sending chunk {chunk_idx} ({len(chunk_data)} bytes)")
        
        future = self._executor.submit(self._transcribe_chunk, chunk_idx, chunk_data)
        self._pending_futures.append(future)
    
    def _transcribe_chunk(self, chunk_idx: int, audio_data: bytes) -> tuple:
        """Transcribe a single chunk via REST API."""
        try:
            t0 = time.time()
            
            # Convert raw PCM to WAV format
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.CHANNELS)
                wav_file.setsampwidth(self.SAMPLE_WIDTH)
                wav_file.setframerate(self.SAMPLE_RATE)
                wav_file.writeframes(audio_data)
            wav_bytes = wav_buffer.getvalue()
            
            # Encode to base64
            audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')
            
            # Build prompt based on language
            if self.language == "auto":
                prompt = (
                    "Transcribe this audio exactly as spoken. "
                    "Use Cyrillic for Russian words and Latin script for English technical terms, brand names, acronyms, and anglicisms. "
                    "Do not transliterate English terms into Cyrillic. "
                    "Normalize keyboard shortcuts in the form 'Ctrl + Shift + V', 'Alt + 1', 'Ctrl + C'. "
                    "Add natural punctuation and capitalization. "
                    "Return ONLY the final transcribed text."
                )
            else:
                prompt = (
                    f"Transcribe this audio in {self.language}. "
                    "Use Cyrillic for Russian words and Latin script for English technical terms, brand names, acronyms, and anglicisms "
                    "(for example: Gemini, Python, API, iPhone, Telegram, OpenAI). "
                    "Do not transliterate English terms into Cyrillic. "
                    "Normalize keyboard shortcuts in the form 'Ctrl + Shift + V', 'Alt + 1', 'Ctrl + C'. "
                    "Add natural punctuation and capitalization. "
                    "Return ONLY the final transcribed text."
                )
            
            # REST API request
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "audio/wav", "data": audio_base64}}
                    ]
                }]
            }
            
            # Proxy support
            proxies = None
            if self.proxy_url:
                proxies = {"http": self.proxy_url, "https": self.proxy_url}
            
            response = requests.post(url, json=payload, timeout=30, proxies=proxies)
            
            if response.status_code != 200:
                log.error(f"[CHUNKED] Chunk {chunk_idx} API error: {response.status_code}")
                return (chunk_idx, "")
            
            result = response.json()
            text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
            
            t1 = time.time()
            log.info(f"[CHUNKED] Chunk {chunk_idx} done in {t1-t0:.2f}s: '{text[:50]}...'")
            
            # Store result
            with self._results_lock:
                self._results[chunk_idx] = text
            
            # Callback
            if self._on_chunk_result:
                self._on_chunk_result(chunk_idx, text)
            
            return (chunk_idx, text)
            
        except Exception as e:
            log.error(f"[CHUNKED] Chunk {chunk_idx} error: {e}")
            if self._on_error:
                self._on_error(str(e))
            return (chunk_idx, "")
    
    def stop(self) -> str:
        """Stop transcriber and return final combined text."""
        self._is_active = False
        log.info("[CHUNKED] Stopping...")
        
        # Send any remaining audio in buffer
        with self._buffer_lock:
            if self._audio_buffer:
                remaining = b''.join(self._audio_buffer)
                if len(remaining) > self.SAMPLE_RATE * self.SAMPLE_WIDTH:  # At least 1 second
                    chunk_idx = self._chunk_index
                    self._chunk_index += 1
                    log.info(f"[CHUNKED] Sending final chunk {chunk_idx} ({len(remaining)} bytes)")
                    future = self._executor.submit(self._transcribe_chunk, chunk_idx, remaining)
                    self._pending_futures.append(future)
                self._audio_buffer = []
        
        # Wait for all pending requests
        log.info(f"[CHUNKED] Waiting for {len(self._pending_futures)} pending requests...")
        t0 = time.time()
        
        for future in as_completed(self._pending_futures, timeout=30):
            try:
                future.result()
            except Exception as e:
                log.error(f"[CHUNKED] Future error: {e}")
        
        t1 = time.time()
        log.info(f"[CHUNKED] All requests done in {t1-t0:.2f}s")
        
        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        
        # Combine results in order
        final_text = self._combine_results()
        log.info(f"[CHUNKED] Final text: {len(final_text)} chars")
        
        return final_text
    
    def _combine_results(self) -> str:
        """Combine chunk results in correct order."""
        with self._results_lock:
            if not self._results:
                return ""
            
            # Sort by chunk index and join
            sorted_chunks = sorted(self._results.items())
            texts = [text for _, text in sorted_chunks if text]
            
            # Join with space, avoiding double spaces
            combined = ' '.join(texts)
            # Clean up multiple spaces
            while '  ' in combined:
                combined = combined.replace('  ', ' ')
            
            return combined.strip()
    
    def get_partial_result(self) -> str:
        """Get current partial result (for real-time display)."""
        return self._combine_results()
