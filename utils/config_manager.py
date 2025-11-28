"""Configuration manager for persisting application settings."""
import json
import os
from typing import Any, Optional


class ConfigManager:
    """Manages application configuration persistence."""
    
    DEFAULT_SETTINGS = {
        "provider": "gemini",
        "api_keys": {
            "gemini": "",
            "openrouter": "",
            "openai": ""
        },
        "model": "gemini-2.5-flash",
        "hotkey": "ctrl+alt",
        "hotkey_mode": "toggle",
        "audio_device": None,
        "output_mode": "inject",
        "typing_speed": 50,
        "sound_enabled": True,
        "show_stats": True,
        "widget_position": {"x": None, "y": None},
        "theme": "gemini"
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize with config file path.
        
        Args:
            config_path: Path to config file. If None, uses %APPDATA%/GeminiVoiceWriter/settings.json
        """
        if config_path is None:
            app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = os.path.join(app_data, 'GeminiVoiceWriter')
            os.makedirs(config_dir, exist_ok=True)
            self.config_path = os.path.join(config_dir, 'settings.json')
        else:
            self.config_path = config_path
            
        self._settings: dict = {}
        self.load()
    
    def load(self) -> dict:
        """Load settings from JSON file.
        
        Returns:
            Dictionary of settings. Returns defaults if file doesn't exist.
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._settings = self._merge_with_defaults(loaded)
            else:
                self._settings = self.DEFAULT_SETTINGS.copy()
        except (json.JSONDecodeError, IOError):
            self._settings = self.DEFAULT_SETTINGS.copy()
        
        return self._settings.copy()
    
    def _merge_with_defaults(self, loaded: dict) -> dict:
        """Merge loaded settings with defaults to ensure all keys exist."""
        result = self.DEFAULT_SETTINGS.copy()
        
        for key, value in loaded.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = {**result[key], **value}
                else:
                    result[key] = value
        
        return result
    
    def save(self, settings: Optional[dict] = None) -> None:
        """Save settings to JSON file.
        
        Args:
            settings: Settings dict to save. If None, saves current settings.
        """
        if settings is not None:
            self._settings = settings
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._settings, f, indent=2, ensure_ascii=False)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value by key.
        
        Args:
            key: Setting key (supports dot notation for nested keys, e.g., 'api_keys.gemini')
            default: Default value if key doesn't exist
            
        Returns:
            Setting value or default
        """
        keys = key.split('.')
        value = self._settings
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set setting value.
        
        Args:
            key: Setting key (supports dot notation for nested keys)
            value: Value to set
        """
        keys = key.split('.')
        target = self._settings
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
    
    def get_all(self) -> dict:
        """Get all settings.
        
        Returns:
            Copy of all settings
        """
        return self._settings.copy()
