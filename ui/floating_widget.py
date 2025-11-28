"""Floating widget with Gemini theme - main UI component."""
from enum import Enum
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QMouseEvent, QPainter, QColor, QLinearGradient, QPen

from utils.config_manager import ConfigManager


class WidgetState(Enum):
    """Widget visual states."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


class FloatingWidget(QWidget):
    """Floating always-on-top widget with Gemini theme."""
    
    # Signals
    recording_toggled = pyqtSignal()
    settings_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    
    # Gemini theme colors
    COLORS = {
        'background': '#0f0f23',
        'background_light': '#1a1a2e',
        'accent_purple': '#8b5cf6',
        'accent_blue': '#3b82f6',
        'text': '#ffffff',
        'text_dim': '#9ca3af',
        'success': '#22c55e',
        'error': '#ef4444',
        'recording': '#ef4444',
    }
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()
        
        self.config = config_manager or ConfigManager()
        self._state = WidgetState.IDLE
        self._drag_position: Optional[QPoint] = None
        self._stats_text = ""
        
        self._setup_window()
        self._setup_ui()
        self._apply_styles()
        self._restore_position()
    
    def _setup_window(self):
        """Configure window properties."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 60)
    
    def _setup_ui(self):
        """Create UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)
        
        # Status indicator (animated dot)
        self.status_indicator = QLabel("●")
        self.status_indicator.setObjectName("statusIndicator")
        self.status_indicator.setFixedWidth(20)
        layout.addWidget(self.status_indicator)
        
        # Status text
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label, 1)
        
        # Record button
        self.record_btn = QPushButton("🎤")
        self.record_btn.setObjectName("recordButton")
        self.record_btn.setFixedSize(36, 36)
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.clicked.connect(self.recording_toggled.emit)
        layout.addWidget(self.record_btn)
        
        # Settings button
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)
        
        # Minimize button
        self.minimize_btn = QPushButton("−")
        self.minimize_btn.setObjectName("minimizeButton")
        self.minimize_btn.setFixedSize(24, 24)
        self.minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimize_btn.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.minimize_btn)
    
    def _apply_styles(self):
        """Apply Gemini theme styles."""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
            
            QLabel#statusIndicator {{
                color: {self.COLORS['accent_purple']};
                font-size: 16px;
            }}
            
            QLabel#statusLabel {{
                color: {self.COLORS['text']};
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
            }}
            
            QPushButton {{
                background-color: {self.COLORS['background_light']};
                color: {self.COLORS['text']};
                border: none;
                border-radius: 18px;
                font-size: 16px;
            }}
            
            QPushButton:hover {{
                background-color: {self.COLORS['accent_purple']};
            }}
            
            QPushButton#minimizeButton {{
                background-color: transparent;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
            }}
            
            QPushButton#minimizeButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
        """)
    
    def paintEvent(self, event):
        """Custom paint for gradient background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create gradient background
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor(self.COLORS['background']))
        gradient.setColorAt(1, QColor(self.COLORS['background_light']))
        
        # Draw rounded rectangle
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(self.COLORS['accent_purple']), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 15, 15)
    
    def set_state(self, state: WidgetState) -> None:
        """Update widget visual state."""
        self._state = state
        
        state_config = {
            WidgetState.IDLE: ("●", self.COLORS['accent_purple'], "Ready"),
            WidgetState.RECORDING: ("●", self.COLORS['recording'], "Recording..."),
            WidgetState.PROCESSING: ("◐", self.COLORS['accent_blue'], "Processing..."),
            WidgetState.SUCCESS: ("✓", self.COLORS['success'], "Done!"),
            WidgetState.ERROR: ("✗", self.COLORS['error'], "Error"),
        }
        
        indicator, color, text = state_config.get(state, state_config[WidgetState.IDLE])
        
        self.status_indicator.setText(indicator)
        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
        self.status_label.setText(text)
        
        # Update record button appearance
        if state == WidgetState.RECORDING:
            self.record_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.COLORS['recording']};
                    color: white;
                    border: none;
                    border-radius: 18px;
                }}
            """)
        else:
            self.record_btn.setStyleSheet("")
    
    def show_stats(self, duration: float, cost: float) -> None:
        """Display transcription statistics."""
        self._stats_text = f"{duration:.1f}s | ${cost:.4f}"
        self.status_label.setText(f"Done! ({self._stats_text})")
    
    def show_error(self, message: str) -> None:
        """Display error message."""
        self.set_state(WidgetState.ERROR)
        self.status_label.setText(f"Error: {message[:30]}...")
    
    # Drag functionality
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_position = None
        self.save_position()
    
    def save_position(self) -> None:
        """Persist current position to config."""
        pos = self.pos()
        self.config.set("widget_position.x", pos.x())
        self.config.set("widget_position.y", pos.y())
        self.config.save()
    
    def _restore_position(self) -> None:
        """Restore position from config."""
        x = self.config.get("widget_position.x")
        y = self.config.get("widget_position.y")
        
        if x is not None and y is not None:
            self.move(x, y)
        else:
            # Center at top of screen
            screen = QApplication.primaryScreen().availableGeometry()
            self.move((screen.width() - self.width()) // 2, 50)
