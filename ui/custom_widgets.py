from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

class HotkeyInput(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Нажмите для записи горячей клавиши...")
        self.setReadOnly(True)  # Prevent manual typing
        self.setMinimumHeight(44)  # Ensure proper height
        self.current_hotkey = ""

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self.clear()
            self.current_hotkey = ""
            return

        # Ignore standalone modifiers
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        # Build string
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")

        # Map Qt key to string
        from PyQt6.QtGui import QKeySequence
        key_text = QKeySequence(key).toString().lower()
        
        # Handle special cases or empty text
        if not key_text:
            # Fallback for common keys if keyToString fails or is weird
            if key == Qt.Key.Key_Space: key_text = "space"
            elif key == Qt.Key.Key_Backspace: key_text = "backspace"
            elif key == Qt.Key.Key_Tab: key_text = "tab"
            elif key == Qt.Key.Key_Return: key_text = "enter"
            # Function keys
            elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
                key_text = f"f{key - Qt.Key.Key_F1 + 1}"
            # Tilde/Backtick
            elif key == Qt.Key.Key_QuoteLeft: key_text = "`"
            
        parts.append(key_text)
        
        hotkey_str = "+".join(parts)
        self.setText(hotkey_str)
        self.current_hotkey = hotkey_str
        
        # Don't propagate to parent (prevents other shortcuts from firing while recording)
        event.accept()

    def mousePressEvent(self, event):
        # Focus on click
        self.setFocus()
        super().mousePressEvent(event)
