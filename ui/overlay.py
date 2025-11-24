from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
import sys

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Fixed size for the bubble
        self.setFixedSize(64, 64)
        
        # Position bottom right
        self.update_position()
        
        # State
        self.state = "HIDDEN" # HIDDEN, RECORDING, TRANSCRIBING, SUCCESS
        self.pulse_value = 0
        self.spinner_angle = 0
        self.stats_text = ""
        
        # Timers
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.update_pulse)
        self.pulse_timer.setInterval(50)
        
        self.spinner_timer = QTimer()
        self.spinner_timer.timeout.connect(self.update_spinner)
        self.spinner_timer.setInterval(30)
        
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_overlay)

    def update_position(self):
        screen = QApplication.primaryScreen().availableGeometry()
        # 20px padding from bottom right
        self.move(screen.width() - self.width() - 20, screen.height() - self.height() - 20)

    def show_recording(self):
        self.state = "RECORDING"
        self.pulse_value = 0
        self.pulse_timer.start()
        self.spinner_timer.stop()
        self.hide_timer.stop()
        self.show()
        self.update()

    def show_transcribing(self):
        self.state = "TRANSCRIBING"
        self.pulse_timer.stop()
        self.spinner_timer.start()
        self.hide_timer.stop()
        self.show()
        self.update()

    def show_success(self, stats_text=""):
        self.state = "SUCCESS"
        self.stats_text = stats_text
        self.pulse_timer.stop()
        self.spinner_timer.stop()
        self.update()
        # Hide after 5 seconds
        self.hide_timer.start(5000) 

    def hide_overlay(self):
        self.state = "HIDDEN"
        self.hide()

    def update_pulse(self):
        self.pulse_value += 0.2
        if self.pulse_value > 2 * 3.14159:
            self.pulse_value = 0
        self.update()

    def update_spinner(self):
        self.spinner_angle += 10
        if self.spinner_angle >= 360:
            self.spinner_angle = 0
        self.update()

    def paintEvent(self, event):
        if self.state == "HIDDEN":
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # Scale factor approx 0.4 (1/2.5)
        # Original Background Radius: 40 -> 16
        bg_radius = 16
        
        # Background Bubble
        painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(center_x - bg_radius), int(center_y - bg_radius), bg_radius * 2, bg_radius * 2)

        if self.state == "RECORDING":
            # Pulsing Red Circle
            # Original Radius: 30 -> 12
            base_radius = 12
            import math
            pulse_scale = 1.0 + 0.2 * math.sin(self.pulse_value)
            r = base_radius * pulse_scale
            
            painter.setBrush(QBrush(QColor(255, 50, 50)))
            painter.drawEllipse(QRectF(center_x - r, center_y - r, 2*r, 2*r))

        elif self.state == "TRANSCRIBING":
            # Spinning Loader
            # Original Rect: 40x40 -> 16x16
            # Pen width: 4 -> 2
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            loader_radius = 8
            rect = QRectF(center_x - loader_radius, center_y - loader_radius, loader_radius * 2, loader_radius * 2)
            painter.drawArc(rect, -self.spinner_angle * 16, 270 * 16)

        elif self.state == "SUCCESS":
            offset_y = 0
            if self.stats_text:
                # Draw Text Top
                painter.setPen(QPen(QColor(255, 255, 255)))
                font = painter.font()
                font.setPointSize(7) # Smaller font
                font.setBold(True)
                painter.setFont(font)
                
                # Position text above center
                text_rect = QRectF(0, center_y - 25, self.width(), 20)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.stats_text)
                
                offset_y = 5 # Push checkmark down slightly if text exists

            # Green Checkmark
            # Original: (-15, -10) -> (-5, 0) -> (15, -25) relative to center
            # Scale 0.4: (-6, -4) -> (-2, 0) -> (6, -10)
            # Pen width: 5 -> 2
            
            painter.setPen(QPen(QColor(50, 255, 50), 2))
            path = QPainterPath()
            
            # Adjust center for checkmark position
            check_center_y = center_y + offset_y
            
            path.moveTo(center_x - 6, check_center_y - 2) # Start
            path.lineTo(center_x - 2, check_center_y + 2) # Bottom
            path.lineTo(center_x + 6, check_center_y - 8) # End
            painter.drawPath(path)
