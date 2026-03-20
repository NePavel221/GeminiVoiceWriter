"""Global hotkey management with toggle and hold-to-record modes."""
import re
import threading
import time
from typing import Callable, Optional

import keyboard


class HotkeyManager:
    """System-wide hotkey registration and handling with dual modes."""
    
    # Valid modifier keys
    VALID_MODIFIERS = {'ctrl', 'alt', 'shift', 'windows', 'win'}
    
    # Valid special keys
    VALID_SPECIAL_KEYS = {
        'space', 'enter', 'tab', 'backspace', 'delete', 'escape', 'esc',
        'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
        'insert', 'pause', 'capslock', 'numlock', 'scrolllock', 'printscreen',
        'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12'
    }
    
    def __init__(self, mode: str = "toggle"):
        """Initialize with recording mode.
        
        Args:
            mode: 'toggle' for press-to-start/press-to-stop, 
                  'hold' for hold-to-record
        """
        self._mode = mode
        self._hotkey: Optional[str] = None
        self._running = False
        self._last_trigger_time = 0
        self._cooldown = 1.0  # Prevent double triggering (1 second)
        
        # Callbacks
        self.on_press: Optional[Callable[[], None]] = None
        self.on_release: Optional[Callable[[], None]] = None
        
        # For hold mode
        self._key_held = False
        self._hook = None
    
    @property
    def mode(self) -> str:
        """Get current recording mode."""
        return self._mode
    
    @property
    def hotkey(self) -> Optional[str]:
        """Get current hotkey string."""
        return self._hotkey
    
    @property
    def is_running(self) -> bool:
        """Check if hotkey listener is active."""
        return self._running
    
    def set_mode(self, mode: str) -> None:
        """Set recording mode.
        
        Args:
            mode: 'toggle' or 'hold'
        """
        if mode not in ('toggle', 'hold'):
            raise ValueError(f"Invalid mode: {mode}. Must be 'toggle' or 'hold'")
        
        was_running = self._running
        if was_running:
            self.unregister()
        
        self._mode = mode
        
        if was_running and self._hotkey:
            self.register(self._hotkey)
    
    def register(self, hotkey: str) -> bool:
        """Register hotkey for listening.
        
        Args:
            hotkey: Hotkey string (e.g., 'ctrl+alt+r', 'f9')
            
        Returns:
            True if registration successful
        """
        valid, error = self.validate_hotkey(hotkey)
        if not valid:
            print(f"Invalid hotkey: {error}")
            return False
        
        # Unregister previous hotkey
        if self._running:
            self.unregister()
        
        self._hotkey = hotkey.lower()
        
        try:
            if self._mode == 'toggle':
                keyboard.add_hotkey(self._hotkey, self._on_toggle_press)
            else:  # hold mode
                # For hold mode, we need to track press and release
                keyboard.on_press_key(
                    self._get_trigger_key(self._hotkey),
                    self._on_hold_press,
                    suppress=False
                )
                keyboard.on_release_key(
                    self._get_trigger_key(self._hotkey),
                    self._on_hold_release,
                    suppress=False
                )
            
            self._running = True
            print(f"Hotkey '{self._hotkey}' registered in {self._mode} mode")
            return True
            
        except Exception as e:
            print(f"Failed to register hotkey: {e}")
            return False
    
    def unregister(self) -> None:
        """Unregister current hotkey."""
        if not self._running:
            return
        
        try:
            if self._hotkey:
                if self._mode == 'toggle':
                    keyboard.remove_hotkey(self._hotkey)
                else:
                    trigger_key = self._get_trigger_key(self._hotkey)
                    keyboard.unhook_key(trigger_key)
        except Exception as e:
            print(f"Error unregistering hotkey: {e}")
        
        self._running = False
        self._key_held = False
    
    def _on_toggle_press(self) -> None:
        """Handle hotkey press in toggle mode."""
        current_time = time.time()
        if current_time - self._last_trigger_time < self._cooldown:
            return
        
        self._last_trigger_time = current_time
        
        if self.on_press:
            self.on_press()
    
    def _on_hold_press(self, event) -> None:
        """Handle key press in hold mode."""
        if self._key_held:
            return
        
        # Check if modifiers are held
        if not self._check_modifiers():
            return
        
        current_time = time.time()
        if current_time - self._last_trigger_time < self._cooldown:
            return
        
        self._last_trigger_time = current_time
        self._key_held = True
        
        if self.on_press:
            self.on_press()
    
    def _on_hold_release(self, event) -> None:
        """Handle key release in hold mode."""
        if not self._key_held:
            return
        
        self._key_held = False
        
        if self.on_release:
            self.on_release()
    
    def _check_modifiers(self) -> bool:
        """Check if required modifier keys are pressed."""
        if not self._hotkey:
            return False
        
        parts = self._hotkey.lower().split('+')
        modifiers = [p for p in parts if p in self.VALID_MODIFIERS]
        
        for mod in modifiers:
            mod_key = 'win' if mod == 'windows' else mod
            if not keyboard.is_pressed(mod_key):
                return False
        
        return True
    
    def _get_trigger_key(self, hotkey: str) -> str:
        """Extract the trigger key from hotkey string."""
        parts = hotkey.lower().split('+')
        # Return the last non-modifier key
        for part in reversed(parts):
            if part not in self.VALID_MODIFIERS:
                return part
        return parts[-1]
    
    @classmethod
    def validate_hotkey(cls, hotkey: str) -> tuple[bool, str]:
        """Validate hotkey string format.
        
        Args:
            hotkey: Hotkey string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not hotkey or not hotkey.strip():
            return False, "Hotkey cannot be empty"
        
        hotkey = hotkey.lower().strip()
        parts = hotkey.split('+')
        
        if len(parts) == 0:
            return False, "Invalid hotkey format"
        
        modifiers = []
        keys = []
        
        for part in parts:
            part = part.strip()
            if not part:
                return False, "Empty part in hotkey"
            
            if part in cls.VALID_MODIFIERS:
                modifiers.append(part)
            elif part in cls.VALID_SPECIAL_KEYS:
                keys.append(part)
            elif len(part) == 1 and part.isalnum():
                keys.append(part)
            else:
                return False, f"Invalid key: {part}"
        
        if len(keys) == 0:
            return False, "Hotkey must include at least one non-modifier key"
        
        if len(keys) > 1:
            return False, "Hotkey can only have one trigger key"
        
        return True, ""
    
    def __del__(self):
        """Cleanup on destruction."""
        self.unregister()
