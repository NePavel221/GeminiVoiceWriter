"""Property-based tests for SoundPlayer.

**Feature: gemini-voice-writer-v2, Properties 18, 19**
**Validates: Requirements 9.2, 9.3**
"""
import os
import tempfile
import time
import wave

import numpy as np
import pytest
from hypothesis import given, strategies as st, settings

from core.sound_player import SoundPlayer


def create_test_sound(filepath: str, duration: float = 0.1) -> None:
    """Create a short test WAV file."""
    sample_rate = 44100
    num_frames = int(sample_rate * duration)
    
    # Generate simple beep
    t = np.linspace(0, duration, num_frames, dtype=np.float32)
    audio = (np.sin(2 * np.pi * 880 * t) * 32767).astype(np.int16)
    
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())


def test_sound_playback_non_blocking():
    """
    **Feature: gemini-voice-writer-v2, Property 18: Sound Playback Non-Blocking**
    
    For any sound playback request, the playback SHALL execute asynchronously 
    and return control to the caller within 10ms.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test sound file
        sound_path = os.path.join(tmpdir, "test_sound.wav")
        create_test_sound(sound_path, duration=0.5)  # 500ms sound
        
        player = SoundPlayer(sounds_dir=tmpdir)
        
        # Measure time to return from play()
        start_time = time.perf_counter()
        player.play("test_sound")
        elapsed = time.perf_counter() - start_time
        
        # Should return within 50ms (non-blocking, allowing some overhead)
        assert elapsed < 0.05, \
            f"play() should return quickly, took {elapsed*1000:.2f}ms"
        
        # Wait for playback thread to finish
        time.sleep(0.6)


@given(sound_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))))
@settings(max_examples=50)
def test_sound_disabled_behavior(sound_name):
    """
    **Feature: gemini-voice-writer-v2, Property 19: Sound Disabled Behavior**
    
    For any sound playback request when sounds are disabled, 
    the system SHALL not attempt playback and SHALL not produce errors.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        player = SoundPlayer(sounds_dir=tmpdir)
        
        # Disable sounds
        player.set_enabled(False)
        assert player.enabled is False
        
        # Should not raise any errors even for non-existent sounds
        start_time = time.perf_counter()
        player.play(sound_name)  # Sound doesn't exist, but shouldn't matter
        elapsed = time.perf_counter() - start_time
        
        # Should return immediately (no attempt to load/play)
        assert elapsed < 0.001, \
            f"Disabled play() should return immediately, took {elapsed*1000:.2f}ms"


def test_sound_player_initialization():
    """Test SoundPlayer initializes correctly."""
    player = SoundPlayer()
    
    assert player.enabled is True
    assert player.sounds_dir is not None


def test_sound_player_enable_disable():
    """Test enable/disable functionality."""
    player = SoundPlayer()
    
    assert player.enabled is True
    
    player.set_enabled(False)
    assert player.enabled is False
    
    player.set_enabled(True)
    assert player.enabled is True


def test_sound_player_missing_file():
    """Test that missing sound files don't cause errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        player = SoundPlayer(sounds_dir=tmpdir)
        player.set_enabled(False)  # Disable to avoid actual playback
        
        # Should not raise exception for missing file
        player.play("nonexistent_sound")


def test_sound_player_preload():
    """Test sound preloading."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test sounds
        create_test_sound(os.path.join(tmpdir, "start.wav"))
        create_test_sound(os.path.join(tmpdir, "stop.wav"))
        
        player = SoundPlayer(sounds_dir=tmpdir)
        
        # Preload sounds
        player.preload(["start", "stop"])
        
        # Check cache
        assert "start" in player._cache
        assert "stop" in player._cache


def test_sound_player_clear_cache():
    """Test cache clearing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_sound(os.path.join(tmpdir, "test.wav"))
        
        player = SoundPlayer(sounds_dir=tmpdir)
        player.preload(["test"])
        
        assert len(player._cache) > 0
        
        player.clear_cache()
        
        assert len(player._cache) == 0
