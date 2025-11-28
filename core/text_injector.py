"""Text injection via keyboard simulation and clipboard."""
import time
from typing import Optional

import pyperclip
from pynput.keyboard import Controller, Key


class TextInjector:
    """Simulates keyboard input to type text into active window."""
    
    def __init__(self, typing_speed: int = 50):
        """Initialize with typing speed.
        
        Args:
            typing_speed: Characters per second (0 for instant)
        """
        self._typing_speed = typing_speed
        self._keyboard = Controller()
    
    @property
    def typing_speed(self) -> int:
        """Get current typing speed."""
        return self._typing_speed
    
    def set_typing_speed(self, speed: int) -> None:
        """Set typing speed.
        
        Args:
            speed: Characters per second (0 for instant)
        """
        self._typing_speed = max(0, speed)
    
    def inject(self, text: str, use_clipboard: bool = False) -> bool:
        """Type text into active window.
        
        Args:
            text: Text to type
            use_clipboard: If True, use clipboard paste instead of typing
            
        Returns:
            True if injection successful
        """
        if not text:
            return True
        
        try:
            if use_clipboard:
                return self._inject_via_clipboard(text)
            else:
                return self._inject_via_typing(text)
        except Exception as e:
            print(f"Text injection failed: {e}")
            # Fallback to clipboard
            try:
                return self._inject_via_clipboard(text)
            except Exception as e2:
                print(f"Clipboard fallback also failed: {e2}")
                return False
    
    def _inject_via_typing(self, text: str) -> bool:
        """Type text character by character.
        
        Args:
            text: Text to type
            
        Returns:
            True if successful
        """
        delay = 1.0 / self._typing_speed if self._typing_speed > 0 else 0
        
        for char in text:
            try:
                self._keyboard.type(char)
                if delay > 0:
                    time.sleep(delay)
            except Exception as e:
                print(f"Error typing character '{char}': {e}")
                # Continue with remaining characters
        
        return True
    
    def _inject_via_clipboard(self, text: str) -> bool:
        """Inject text via clipboard paste.
        
        Args:
            text: Text to paste
            
        Returns:
            True if successful
        """
        # Save current clipboard content
        try:
            original_clipboard = pyperclip.paste()
        except Exception:
            original_clipboard = None
        
        try:
            # Copy text to clipboard
            pyperclip.copy(text)
            
            # Small delay to ensure clipboard is updated
            time.sleep(0.05)
            
            # Simulate Ctrl+V
            self._keyboard.press(Key.ctrl)
            self._keyboard.press('v')
            self._keyboard.release('v')
            self._keyboard.release(Key.ctrl)
            
            # Small delay after paste
            time.sleep(0.1)
            
            return True
            
        finally:
            # Restore original clipboard (optional)
            # Commented out to keep transcribed text in clipboard
            # if original_clipboard is not None:
            #     time.sleep(0.1)
            #     pyperclip.copy(original_clipboard)
            pass
    
    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard without pasting.
        
        Args:
            text: Text to copy
            
        Returns:
            True if successful
        """
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")
            return False
    
    def paste_from_clipboard(self) -> bool:
        """Simulate Ctrl+V to paste from clipboard.
        
        Returns:
            True if successful
        """
        try:
            self._keyboard.press(Key.ctrl)
            self._keyboard.press('v')
            self._keyboard.release('v')
            self._keyboard.release(Key.ctrl)
            return True
        except Exception as e:
            print(f"Failed to paste: {e}")
            return False
    
    @staticmethod
    def get_clipboard_content() -> Optional[str]:
        """Get current clipboard content.
        
        Returns:
            Clipboard text or None if failed
        """
        try:
            return pyperclip.paste()
        except Exception:
            return None
