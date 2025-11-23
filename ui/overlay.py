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
        self.setFixedSize(160, 120)
        
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
        radius = 30

        # Background Bubble
        painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(center_x - 40), int(center_y - 40), 80, 80)

        if self.state == "RECORDING":
            # Pulsing Red Circle
            import math
            pulse_scale = 1.0 + 0.2 * math.sin(self.pulse_value)
            r = radius * pulse_scale
            
            painter.setBrush(QBrush(QColor(255, 50, 50)))
            painter.drawEllipse(QRectF(center_x - r, center_y - r, 2*r, 2*r))

        elif self.state == "TRANSCRIBING":
            # Spinning Loader
            painter.setPen(QPen(QColor(255, 255, 255), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(center_x - 20, center_y - 20, 40, 40)
            painter.drawArc(rect, -self.spinner_angle * 16, 270 * 16)

        elif self.state == "SUCCESS":
            # Green Checkmark
            painter.setPen(QPen(QColor(50, 255, 50), 5))
            path = QPainterPath()
            path.moveTo(center_x - 15, center_y - 10)
            path.lineTo(center_x - 5, center_y)
            path.lineTo(center_x + 15, center_y - 25)
            painter.drawPath(path)
            
            if self.stats_text:
                painter.setPen(QPen(QColor(255, 255, 255)))
                font = painter.font()
                font.setPointSize(10)
                font.setBold(True)
                painter.setFont(font)
                
                rect = QRectF(0, center_y + 10, self.width(), 40)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.stats_text)
