"""Non-blocking audio recorder using sounddevice."""
import os
import tempfile
import threading
import wave
from typing import Optional, Callable

import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Non-blocking audio recorder with device selection support."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = 'int16',
        output_dir: Optional[str] = None
    ):
        """Initialize recorder with audio settings.
        
        Args:
            sample_rate: Sample rate in Hz (default 16kHz for speech)
            channels: Number of audio channels (1 for mono)
            dtype: Audio data type
            output_dir: Directory for output files (default: temp dir)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.output_dir = output_dir or tempfile.gettempdir()
        
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._device_id: Optional[int] = None
        self._lock = threading.Lock()
        
        # Callbacks
        self.on_recording_started: Optional[Callable[[], None]] = None
        self.on_recording_stopped: Optional[Callable[[str, float], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording
    
    def get_devices(self) -> list[dict]:
        """List available audio input devices.
        
        Returns:
            List of device dictionaries with 'id', 'name', 'channels' keys
        """
        devices = []
        try:
            device_list = sd.query_devices()
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    devices.append({
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'default': device == sd.query_devices(kind='input')
                    })
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to enumerate devices: {e}")
        return devices
    
    def set_device(self, device_id: Optional[int]) -> None:
        """Set active input device.
        
        Args:
            device_id: Device ID or None for default
        """
        self._device_id = device_id
    
    def start(self) -> bool:
        """Start recording in background.
        
        Returns:
            True if recording started successfully
        """
        if self._recording:
            return False
        
        with self._lock:
            self._frames = []
            self._recording = True
        
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self._device_id,
                callback=self._audio_callback
            )
            self._stream.start()
            
            if self.on_recording_started:
                self.on_recording_started()
            
            return True
            
        except Exception as e:
            self._recording = False
            error_msg = f"Failed to start recording: {e}"
            if self.on_error:
                self.on_error(error_msg)
            
            # Try fallback to default device
            if self._device_id is not None:
                self._device_id = None
                return self.start()
            
            return False
    
    def stop(self) -> tuple[Optional[str], float]:
        """Stop recording and save to file.
        
        Returns:
            Tuple of (filepath, duration) or (None, 0) if failed
        """
        if not self._recording:
            return None, 0.0
        
        with self._lock:
            self._recording = False
        
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
        except Exception as e:
            if self.on_error:
                self.on_error(f"Error stopping stream: {e}")
        
        # Save to file
        filepath, duration = self._save_to_file()
        
        if self.on_recording_stopped and filepath:
            self.on_recording_stopped(filepath, duration)
        
        return filepath, duration
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback for audio stream - runs in separate thread."""
        if status:
            print(f"Audio callback status: {status}")
        
        if self._recording:
            with self._lock:
                self._frames.append(indata.copy())
    
    def _save_to_file(self) -> tuple[Optional[str], float]:
        """Save recorded frames to WAV file.
        
        Returns:
            Tuple of (filepath, duration)
        """
        if not self._frames:
            return None, 0.0
        
        try:
            # Concatenate all frames
            audio_data = np.concatenate(self._frames, axis=0)
            
            # Generate filename
            filepath = os.path.join(
                self.output_dir,
                f"recording_{id(self)}_{len(self._frames)}.wav"
            )
            
            # Save as WAV
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            
            # Calculate duration
            duration = len(audio_data) / self.sample_rate
            
            return filepath, duration
            
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to save recording: {e}")
            return None, 0.0
    
    def __del__(self):
        """Cleanup on destruction."""
        if self._recording:
            self.stop()
