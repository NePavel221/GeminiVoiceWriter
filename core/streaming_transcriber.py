"""Streaming transcriber - uploads audio chunks during recording."""
import os
import io
import wave
import threading
import tempfile
import time
from typing import Optional, Callable
from queue import Queue, Empty

import google.generativeai as genai


class StreamingTranscriber:
    """Transcriber that uploads audio in chunks during recording for faster results."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        genai.configure(api_key=api_key)
        self._genai_model = genai.GenerativeModel(model)
        
        # Streaming state
        self._is_streaming = False
        self._audio_buffer = []
        self._upload_thread: Optional[threading.Thread] = None
        self._uploaded_file = None
        self._upload_lock = threading.Lock()
        
        # Audio params (must match recorder)
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2  # 16-bit
        
        # Temp file for streaming
        self._temp_dir = tempfile.gettempdir()
        self._stream_file = os.path.join(self._temp_dir, "gvw_stream.wav")
    
    def start_streaming(self):
        """Start streaming mode - call this when recording starts."""
        self._is_streaming = True
        self._audio_buffer = []
        self._uploaded_file = None
    
    def add_audio_chunk(self, chunk: bytes):
        """Add audio chunk to buffer. Called during recording."""
        if self._is_streaming:
            with self._upload_lock:
                self._audio_buffer.append(chunk)
    
    def _save_buffer_to_wav(self, frames: list) -> str:
        """Save current buffer to WAV file."""
        with wave.open(self._stream_file, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.sample_width)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
        return self._stream_file

    def finish_and_transcribe(self) -> tuple[str, float]:
        """Finish streaming and get transcription.
        
        Returns:
            Tuple of (transcribed_text, duration_seconds)
        """
        self._is_streaming = False
        
        # Get final buffer
        with self._upload_lock:
            final_frames = list(self._audio_buffer)
            self._audio_buffer = []
        
        if not final_frames:
            return "", 0.0
        
        # Calculate duration
        total_bytes = sum(len(f) for f in final_frames)
        duration = total_bytes / (self.sample_rate * self.channels * self.sample_width)
        
        # Save to file
        audio_path = self._save_buffer_to_wav(final_frames)
        
        # Upload and transcribe
        try:
            audio_file = genai.upload_file(path=audio_path)
            
            response = self._genai_model.generate_content([
                "Please transcribe the following audio file exactly as spoken. "
                "Apply proper punctuation and capitalization. "
                "Return ONLY the transcribed text, no additional commentary.",
                audio_file
            ])
            
            text = response.text.strip() if response.text else ""
            return text, duration
            
        except Exception as e:
            print(f"StreamingTranscriber error: {e}")
            raise
    
    def stop_streaming(self):
        """Cancel streaming without transcribing."""
        self._is_streaming = False
        self._audio_buffer = []
        self._uploaded_file = None


class PreUploadTranscriber:
    """Transcriber that pre-uploads audio file while still recording.
    
    Strategy: After 2 seconds of recording, start uploading what we have.
    When recording stops, we only need to upload the remaining chunk + transcribe.
    """
    
    UPLOAD_DELAY = 1.5  # Start uploading after 1.5 seconds
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        genai.configure(api_key=api_key)
        self._genai_model = genai.GenerativeModel(model)
        
        # State
        self._is_recording = False
        self._audio_frames = []
        self._frames_lock = threading.Lock()
        self._pre_upload_done = False
        self._pre_uploaded_frames_count = 0
        
        # Audio params
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2
        
        self._temp_dir = tempfile.gettempdir()
    
    def start_recording(self):
        """Call when recording starts."""
        self._is_recording = True
        self._audio_frames = []
        self._pre_upload_done = False
        self._pre_uploaded_frames_count = 0
    
    def add_frame(self, frame: bytes):
        """Add audio frame during recording."""
        with self._frames_lock:
            self._audio_frames.append(frame)
    
    def get_frames_copy(self) -> list:
        """Get copy of current frames."""
        with self._frames_lock:
            return list(self._audio_frames)
    
    def transcribe_final(self) -> tuple[str, float]:
        """Transcribe all recorded audio.
        
        Returns:
            Tuple of (text, duration)
        """
        self._is_recording = False
        
        with self._frames_lock:
            frames = list(self._audio_frames)
        
        if not frames:
            return "", 0.0
        
        # Calculate duration
        total_bytes = sum(len(f) for f in frames)
        duration = total_bytes / (self.sample_rate * self.channels * self.sample_width)
        
        # Save to temp file
        temp_file = os.path.join(self._temp_dir, "gvw_final.wav")
        with wave.open(temp_file, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.sample_width)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
        
        # Upload and transcribe
        audio_file = genai.upload_file(path=temp_file)
        
        response = self._genai_model.generate_content([
            "Please transcribe the following audio file exactly as spoken. "
            "Apply proper punctuation and capitalization. "
            "Return ONLY the transcribed text, no additional commentary.",
            audio_file
        ])
        
        text = response.text.strip() if response.text else ""
        return text, duration
