"""Non-blocking sound playback for audio feedback."""
import os
import threading
from typing import Optional

import numpy as np


class SoundPlayer:
    """Non-blocking sound playback for UI feedback sounds."""
    
    def __init__(self, sounds_dir: Optional[str] = None):
        """Initialize with sounds directory path.
        
        Args:
            sounds_dir: Directory containing WAV sound files
        """
        self.sounds_dir = sounds_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'assets', 'sounds'
        )
        self._enabled = True
        self._cache: dict[str, np.ndarray] = {}
        self._sample_rate = 44100
    
    @property
    def enabled(self) -> bool:
        """Check if sound playback is enabled."""
        return self._enabled
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable sound playback.
        
        Args:
            enabled: True to enable, False to disable
        """
        self._enabled = enabled
    
    def play(self, sound_name: str) -> None:
        """Play sound asynchronously.
        
        Silently fails if disabled, file missing, or playback error.
        
        Args:
            sound_name: Name of sound file (without .wav extension)
        """
        if not self._enabled:
            return
        
        # Run playback in separate thread to avoid blocking
        thread = threading.Thread(
            target=self._play_sound,
            args=(sound_name,),
            daemon=True
        )
        thread.start()
    
    def _play_sound(self, sound_name: str) -> None:
        """Internal method to play sound (runs in thread)."""
        try:
            # Try to get from cache first
            if sound_name in self._cache:
                audio_data = self._cache[sound_name]
            else:
                audio_data = self._load_sound(sound_name)
                if audio_data is None:
                    return
                self._cache[sound_name] = audio_data
            
            # Play using sounddevice
            import sounddevice as sd
            sd.play(audio_data, self._sample_rate)
            sd.wait()  # Wait for playback to finish
            
        except Exception as e:
            # Silently fail - sound feedback is not critical
            print(f"Sound playback error: {e}")
    
    def _load_sound(self, sound_name: str) -> Optional[np.ndarray]:
        """Load sound file from disk.
        
        Args:
            sound_name: Name of sound file (without extension)
            
        Returns:
            Audio data as numpy array or None if failed
        """
        filepath = os.path.join(self.sounds_dir, f"{sound_name}.wav")
        
        if not os.path.exists(filepath):
            print(f"Sound file not found: {filepath}")
            return None
        
        try:
            import wave
            with wave.open(filepath, 'rb') as wf:
                self._sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                audio_bytes = wf.readframes(n_frames)
                
                # Convert to numpy array
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                
                # Normalize to float32 for sounddevice
                audio_data = audio_data.astype(np.float32) / 32768.0
                
                return audio_data
                
        except Exception as e:
            print(f"Failed to load sound {sound_name}: {e}")
            return None
    
    def preload(self, sound_names: list[str]) -> None:
        """Preload sounds into cache for faster playback.
        
        Args:
            sound_names: List of sound names to preload
        """
        for name in sound_names:
            if name not in self._cache:
                audio_data = self._load_sound(name)
                if audio_data is not None:
                    self._cache[name] = audio_data
    
    def clear_cache(self) -> None:
        """Clear the sound cache."""
        self._cache.clear()
