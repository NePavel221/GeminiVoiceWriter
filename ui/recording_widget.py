"""Recording widget in WhisperTyping style with Gemini gradient colors."""
import math
import random
from enum import Enum
from typing import Optional

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QMouseEvent, QPainter, QColor, QLinearGradient, QPen, QBrush, QPainterPath


class RecordingState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


class AudioWaveform(QWidget):
    """Animated audio waveform - 9 bars that react to voice."""
    
    NUM_BARS = 9  # 9 bars for cleaner look
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(90, 32)  # Compact size
        
        self._is_active = False
        self._level = 0.0
        self._target_level = 0.0
        self._bars = [0.15] * self.NUM_BARS
        
        # Animation timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.setInterval(30)  # ~33 FPS
    
    def start(self):
        self._is_active = True
        self._level = 0.0
        self._target_level = 0.0
        self._bars = [0.15] * self.NUM_BARS
        self._timer.start()
        self.update()
    
    def stop(self):
        self._is_active = False
        self._timer.stop()
        self._level = 0.0
        self._bars = [0.15] * self.NUM_BARS
        self.update()
    
    def set_level(self, level: float):
        """Set audio level from actual input (0.0 - 1.0)."""
        # Boost sensitivity - multiply by 6 for better response
        self._target_level = min(1.0, max(0.0, level * 6.0))
    
    def _animate(self):
        # Smooth interpolation of level
        self._level += (self._target_level - self._level) * 0.4
        
        # Update bars based on audio level
        for i in range(self.NUM_BARS):
            if self._is_active:
                # Center bars are taller (bell curve)
                center = self.NUM_BARS / 2
                distance_from_center = abs(i - center) / center
                center_factor = 1.0 - distance_from_center * 0.5
                
                if self._level > 0.05:
                    # Voice detected - bars react to level
                    base = 0.2 + self._level * 0.8 * center_factor
                    # Add randomness for natural look
                    target = base * random.uniform(0.8, 1.2)
                else:
                    # Silence - minimal height
                    target = 0.12 + random.uniform(0, 0.05)
                
                # Smooth interpolation
                self._bars[i] += (target - self._bars[i]) * 0.5
                self._bars[i] = max(0.1, min(1.0, self._bars[i]))
            else:
                self._bars[i] = 0.15
        
        # Decay target level quickly when silent
        self._target_level *= 0.7
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bar_width = 6
        bar_spacing = 4
        total_width = self.NUM_BARS * bar_width + (self.NUM_BARS - 1) * bar_spacing
        start_x = (self.width() - total_width) // 2
        center_y = self.height() // 2
        max_height = self.height() - 4
        
        # Gemini colors for 9 bars
        colors = ["#4285F4", "#5E97F6", "#EA4335", "#F5A623", "#FBBC05", 
                  "#F5A623", "#34A853", "#5E97F6", "#4285F4"]
        
        for i in range(self.NUM_BARS):
            x = start_x + i * (bar_width + bar_spacing)
            
            # Height based on bar value
            height = max(4, int(max_height * self._bars[i]))
            y = center_y - height // 2
            
            # Color from Gemini palette
            if self._is_active:
                color = QColor(colors[i])
            else:
                color = QColor("#6b7280")
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_width, height, 2, 2)


class MicButton(QWidget):
    """Circular microphone button with hover animation and Gemini gradient."""
    
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)  # Smaller to fit hover animation
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._is_recording = False
        self._hover = False
        self._pulse_phase = 0.0
        self._hover_scale = 1.0
        self._gradient_offset = 0.0
        
        # Pulse animation for recording
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._animate_pulse)
        self._pulse_timer.setInterval(30)
        
        # Hover animation
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.setInterval(30)
        self._hover_timer.start()  # Always running for smooth hover
    
    def set_recording(self, recording: bool):
        self._is_recording = recording
        if recording:
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self._pulse_phase = 0.0
        self.update()
    
    def _animate_pulse(self):
        self._pulse_phase += 0.15
        if self._pulse_phase > math.pi * 2:
            self._pulse_phase = 0
        self.update()
    
    def _animate_hover(self):
        # Smooth hover scale animation
        target_scale = 1.1 if self._hover else 1.0
        self._hover_scale += (target_scale - self._hover_scale) * 0.2
        
        # Rotating gradient when hovering
        if self._hover or self._is_recording:
            self._gradient_offset += 0.02
            if self._gradient_offset > 1.0:
                self._gradient_offset = 0.0
        
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center = self.rect().center()
        base_radius = 18  # Smaller base so hover doesn't clip
        radius = int(base_radius * self._hover_scale)
        
        # Gemini gradient border (rotating when hovered)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        
        # Rotate colors based on offset
        colors = [
            ("#4285F4", 0.0),   # Blue
            ("#EA4335", 0.33),  # Red
            ("#FBBC05", 0.66),  # Yellow
            ("#34A853", 1.0),   # Green
        ]
        
        for color, pos in colors:
            new_pos = (pos + self._gradient_offset) % 1.0
            gradient.setColorAt(new_pos, QColor(color))
        
        # Draw gradient ring
        pen_width = 3
        if self._is_recording:
            pulse = 1.0 + 0.2 * math.sin(self._pulse_phase)
            pen_width = int(4 * pulse)
        elif self._hover:
            pen_width = 4
        
        painter.setPen(QPen(QBrush(gradient), pen_width))
        painter.setBrush(QColor("#1a1a2e"))
        painter.drawEllipse(center, radius, radius)
        
        # Draw microphone icon (smaller to fit in smaller button)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._is_recording:
            # Red stop square when recording
            painter.setBrush(QColor("#EA4335"))
            size = int(6 * self._hover_scale)
            painter.drawRoundedRect(center.x() - size, center.y() - size, size * 2, size * 2, 2, 2)
        else:
            # White microphone icon (scales with hover)
            scale = self._hover_scale
            painter.setBrush(QColor("#ffffff"))
            # Mic body - smaller
            w, h = int(4 * scale), int(6 * scale)
            painter.drawRoundedRect(center.x() - w, center.y() - int(9 * scale), w * 2, int(12 * scale), w, w)
            # Mic stand
            painter.drawRect(center.x() - 1, center.y() + int(4 * scale), 2, int(3 * scale))
            painter.drawRect(center.x() - int(5 * scale), center.y() + int(7 * scale), int(10 * scale), 2)
    
    def enterEvent(self, event):
        self._hover = True
    
    def leaveEvent(self, event):
        self._hover = False
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class RecordingWidget(QWidget):
    """Floating recording widget in WhisperTyping style with Gemini colors."""
    
    recording_toggled = pyqtSignal()
    settings_requested = pyqtSignal()
    hide_to_tray_requested = pyqtSignal()  # Hide all windows to tray
    close_app_requested = pyqtSignal()  # Close entire application
    tray_text_changed = pyqtSignal(str)  # Signal for tray tooltip update
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._state = RecordingState.IDLE
        self._recording_seconds = 0.0
        self._processing_seconds = 0.0
        self._last_recording_duration = 0.0  # Store recording duration for processing display
        self._drag_position: Optional[QPoint] = None
        
        # Timers
        self._recording_timer = QTimer()
        self._recording_timer.timeout.connect(self._update_recording_time)
        self._recording_timer.setInterval(100)  # 100ms updates
        
        self._processing_timer = QTimer()
        self._processing_timer.timeout.connect(self._update_processing_time)
        self._processing_timer.setInterval(100)
        
        # Idle timer (can be cancelled when new recording starts)
        self._idle_timer = QTimer()
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self.set_idle)
        
        self._setup_window()
        self._setup_ui()
        self._position_widget()
    
    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(310, 70)  # Compact widget with hide/close buttons
    
    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(12)
        
        # Settings button (left)
        self.settings_btn = QPushButton("Настройки")
        self.settings_btn.setFixedSize(70, 32)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #252540;
                color: #9ca3af;
                border: 1px solid #374151;
                border-radius: 8px;
                font-size: 12px;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                background-color: #374151;
                color: white;
            }
        """)
        main_layout.addWidget(self.settings_btn)
        
        # Center: waveform + status
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)
        
        self.waveform = AudioWaveform()
        center_layout.addWidget(self.waveform, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.status_label = QLabel("Готово")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 12px;
                font-family: 'Segoe UI', sans-serif;
            }
        """)
        center_layout.addWidget(self.status_label)
        
        # Real-time transcription text (hidden by default)
        self.realtime_label = QLabel("")
        self.realtime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.realtime_label.setWordWrap(True)
        self.realtime_label.setMaximumWidth(200)
        self.realtime_label.setStyleSheet("""
            QLabel {
                color: #4285F4;
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
            }
        """)
        self.realtime_label.hide()
        center_layout.addWidget(self.realtime_label)
        
        main_layout.addWidget(center_widget, 1)
        
        # Microphone button
        self.mic_btn = MicButton()
        self.mic_btn.clicked.connect(self.recording_toggled.emit)
        main_layout.addWidget(self.mic_btn)
        
        # Right side: Hide and Close buttons (vertical)
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        # Hide to tray button
        self.hide_btn = QPushButton("−")
        self.hide_btn.setFixedSize(20, 20)
        self.hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_btn.setToolTip("Скрыть в трей")
        self.hide_btn.clicked.connect(self.hide_to_tray_requested.emit)
        self.hide_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9ca3af;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #374151;
                color: white;
            }
        """)
        btn_layout.addWidget(self.hide_btn)
        
        # Close app button
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Закрыть приложение")
        self.close_btn.clicked.connect(self.close_app_requested.emit)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9ca3af;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        btn_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(btn_layout)
    
    def _position_widget(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = 30
        self.move(x, y)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor("#1a1a2e"))
        
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor("#4285F4"))
        gradient.setColorAt(0.33, QColor("#EA4335"))
        gradient.setColorAt(0.66, QColor("#FBBC05"))
        gradient.setColorAt(1.0, QColor("#34A853"))
        
        border_width = 3 if self._state == RecordingState.RECORDING else 2
        
        painter.setPen(QPen(QBrush(gradient), border_width))
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 20, 20)
    
    def set_recording(self):
        # Cancel any pending idle timer from previous session
        self._idle_timer.stop()
        
        self._state = RecordingState.RECORDING
        self._recording_seconds = 0.0
        self.waveform.start()
        self._recording_timer.start()
        self.mic_btn.set_recording(True)
        self._update_status()
        self.update()
        print(f"[WIDGET] set_recording() called, state={self._state}")
    
    def set_processing(self, actual_duration: float = None):
        self._state = RecordingState.PROCESSING
        # Use actual duration from recorder if provided, otherwise use internal timer
        if actual_duration is not None:
            self._last_recording_duration = actual_duration
        else:
            self._last_recording_duration = self._recording_seconds
        self._processing_seconds = 0.0
        self.waveform.stop()
        self._recording_timer.stop()
        self._processing_timer.start()
        self.mic_btn.set_recording(False)
        self._update_status()
        self.update()
    
    def get_recording_duration(self) -> float:
        """Get the last recording duration."""
        return self._last_recording_duration
    
    def set_success(self, transcription_time: float = 0):
        self._state = RecordingState.SUCCESS
        self._processing_timer.stop()
        self.waveform.stop()
        self.mic_btn.set_recording(False)
        # Show recording duration → transcription time
        rec_secs = int(self._last_recording_duration)
        self.status_label.setText(f"✓ {rec_secs}с → {transcription_time:.2f}с")
        self.status_label.setStyleSheet("QLabel { color: #34A853; font-size: 12px; }")
        self.tray_text_changed.emit(f"✓ Готово!")
        self.update()
        # Use managed timer that can be cancelled
        self._idle_timer.start(3000)
    
    def set_idle(self):
        print(f"[WIDGET] set_idle() called, current state={self._state}")
        self._state = RecordingState.IDLE
        self._recording_timer.stop()
        self._processing_timer.stop()
        self.waveform.stop()
        self.mic_btn.set_recording(False)
        self.status_label.setText("Готово")
        self.status_label.setStyleSheet("QLabel { color: #9ca3af; font-size: 12px; }")
        self.tray_text_changed.emit("Gemini Voice Writer")
        self.update()
    
    def set_error(self, message: str = "Error"):
        self._state = RecordingState.ERROR
        self._recording_timer.stop()
        self._processing_timer.stop()
        self.waveform.stop()
        self.mic_btn.set_recording(False)
        self.status_label.setText(f"✗ {message[:20]}")
        self.status_label.setStyleSheet("QLabel { color: #EA4335; font-size: 12px; }")
        self.tray_text_changed.emit(f"✗ Ошибка")
        self.update()
        # Use managed timer that can be cancelled
        self._idle_timer.start(3000)
    
    def _update_recording_time(self):
        self._recording_seconds += 0.1
        self._update_status()
    
    def _update_processing_time(self):
        self._processing_seconds += 0.1
        self._update_status()
    
    def _update_status(self):
        if self._state == RecordingState.RECORDING:
            # Show only whole seconds
            secs = int(self._recording_seconds)
            self.status_label.setText(f"Запись {secs}с")
            self.status_label.setStyleSheet("QLabel { color: #EA4335; font-size: 12px; }")
            # Emit tray text
            self.tray_text_changed.emit(f"🎤 {secs}s")
        elif self._state == RecordingState.PROCESSING:
            # Show recording duration → processing time (like WhisperTyping)
            rec_secs = int(self._last_recording_duration)
            proc_secs = self._processing_seconds
            self.status_label.setText(f"{rec_secs}с → {proc_secs:.1f}с")
            self.status_label.setStyleSheet("QLabel { color: #FBBC05; font-size: 12px; }")
            # Emit tray text
            self.tray_text_changed.emit(f"⏳ {rec_secs}s → {proc_secs:.1f}s")
    
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
    
    def set_realtime_text(self, text: str):
        """Update real-time transcription text."""
        if text:
            # Show last 50 chars with ellipsis
            display_text = text[-50:] if len(text) > 50 else text
            if len(text) > 50:
                display_text = "..." + display_text
            self.realtime_label.setText(display_text)
            self.realtime_label.show()
        else:
            self.realtime_label.hide()
    
    def clear_realtime_text(self):
        """Clear real-time transcription text."""
        self.realtime_label.setText("")
        self.realtime_label.hide()
