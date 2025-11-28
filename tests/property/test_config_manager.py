"""Property-based tests for ConfigManager.

**Feature: gemini-voice-writer-v2, Property 12: Settings Persistence Round-Trip**
**Validates: Requirements 7.2, 7.3**
"""
import os
import tempfile
from hypothesis import given, strategies as st, settings

from utils.config_manager import ConfigManager


# Strategy for generating valid settings dictionaries
settings_strategy = st.fixed_dictionaries({
    "provider": st.sampled_from(["gemini", "openrouter", "openai"]),
    "api_keys": st.fixed_dictionaries({
        "gemini": st.text(min_size=0, max_size=50),
        "openrouter": st.text(min_size=0, max_size=50),
        "openai": st.text(min_size=0, max_size=50)
    }),
    "model": st.text(min_size=1, max_size=30),
    "hotkey": st.text(min_size=1, max_size=20),
    "hotkey_mode": st.sampled_from(["toggle", "hold"]),
    "audio_device": st.one_of(st.none(), st.integers(min_value=0, max_value=10)),
    "output_mode": st.sampled_from(["inject", "clipboard"]),
    "typing_speed": st.integers(min_value=1, max_value=200),
    "sound_enabled": st.booleans(),
    "show_stats": st.booleans(),
    "widget_position": st.fixed_dictionaries({
        "x": st.one_of(st.none(), st.integers(min_value=0, max_value=3000)),
        "y": st.one_of(st.none(), st.integers(min_value=0, max_value=2000))
    }),
    "theme": st.sampled_from(["gemini", "dark", "light"])
})


@given(test_settings=settings_strategy)
@settings(max_examples=100)
def test_settings_roundtrip(test_settings):
    """
    **Feature: gemini-voice-writer-v2, Property 12: Settings Persistence Round-Trip**
    
    For any valid settings dictionary, saving to JSON and loading back 
    SHALL return an equivalent dictionary.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'test_settings.json')
        
        # Save settings
        manager = ConfigManager(config_path=config_path)
        manager.save(test_settings)
        
        # Load settings in new instance
        manager2 = ConfigManager(config_path=config_path)
        loaded = manager2.get_all()
        
        # Verify round-trip
        assert loaded == test_settings, f"Round-trip failed: {test_settings} != {loaded}"


@given(key=st.sampled_from(["provider", "model", "hotkey", "typing_speed", "sound_enabled"]),
       value=st.one_of(st.text(min_size=1, max_size=20), st.integers(), st.booleans()))
@settings(max_examples=100)
def test_get_set_roundtrip(key, value):
    """Test that get/set operations are consistent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'test_settings.json')
        manager = ConfigManager(config_path=config_path)
        
        manager.set(key, value)
        retrieved = manager.get(key)
        
        assert retrieved == value, f"get/set failed for {key}: {value} != {retrieved}"


@given(nested_value=st.text(min_size=0, max_size=50))
@settings(max_examples=100)
def test_nested_key_access(nested_value):
    """Test dot notation for nested keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'test_settings.json')
        manager = ConfigManager(config_path=config_path)
        
        manager.set("api_keys.gemini", nested_value)
        retrieved = manager.get("api_keys.gemini")
        
        assert retrieved == nested_value


def test_missing_file_returns_defaults():
    """Test that missing config file returns default settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'nonexistent.json')
        manager = ConfigManager(config_path=config_path)
        
        settings = manager.get_all()
        assert settings == ConfigManager.DEFAULT_SETTINGS


def test_corrupted_file_returns_defaults():
    """Test that corrupted JSON returns default settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'corrupted.json')
        
        # Write invalid JSON
        with open(config_path, 'w') as f:
            f.write("{ invalid json }")
        
        manager = ConfigManager(config_path=config_path)
        settings = manager.get_all()
        
        assert settings == ConfigManager.DEFAULT_SETTINGS
