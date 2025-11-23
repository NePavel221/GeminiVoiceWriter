from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox,
                             QSystemTrayIcon, QMenu, QApplication, QScrollArea)
from PyQt6.QtCore import pyqtSignal, QObject, Qt, QRectF, QEvent
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
import sys
import threading
import pyautogui
import pyperclip
import json
from ui.overlay import OverlayWindow
from ui.custom_widgets import HotkeyInput

class WorkerSignals(QObject):
    status_update = pyqtSignal(str)
    finished = pyqtSignal(str, float, float) # text, duration, cost
    error = pyqtSignal(str)

class MainWindow(QMainWindow):
    hotkey_triggered = pyqtSignal()

    def __init__(self, recorder, transcriber_class, hotkey_manager_class):
        super().__init__()
        self.recorder = recorder
        self.TranscriberClass = transcriber_class
        self.HotkeyManagerClass = hotkey_manager_class
        
        self.hotkey_manager = None
        self.transcriber = None
        self.is_recording = False
        
        self.setWindowTitle("Gemini Voice Writer")
        self.setGeometry(100, 100, 420, 600)
        
        # Overlay
        self.overlay = OverlayWindow()
        
        self.init_ui()
        self.init_tray()
        self.load_settings()
        
        # Signals
        self.signals = WorkerSignals()
        self.signals.status_update.connect(self.update_status)
        self.signals.finished.connect(self.on_transcription_finished)
        self.signals.error.connect(self.on_error)
        
        # Connect hotkey signal to toggle_recording (ensures execution on Main Thread)
        self.hotkey_triggered.connect(self.toggle_recording)

        # Initialize Hotkey
        self.update_hotkey_listener()
        
        # Apply Styles
        self.apply_styles()

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        # Main Layout with margins
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header_label = QLabel("Gemini Voice Writer")
        header_label.setObjectName("headerLabel")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)
        
        # Scroll Area for Settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setObjectName("settingsScrollArea")
        
        # Settings Container
        settings_widget = QWidget()
        settings_widget.setObjectName("settingsWidget")
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(10)
        
        # API Key Input
        api_key_label = QLabel("GEMINI API KEY")
        api_key_label.setObjectName("fieldLabel")
        settings_layout.addWidget(api_key_label)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Paste your API key here")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        settings_layout.addWidget(self.api_key_input)

        # Hotkey Input
        hotkey_label = QLabel("HOTKEY SHORTCUT")
        hotkey_label.setObjectName("fieldLabel")
        settings_layout.addWidget(hotkey_label)
        
        self.hotkey_input = HotkeyInput()
        self.hotkey_input.setPlaceholderText("Click to record shortcut")
        settings_layout.addWidget(self.hotkey_input)

        # Model Selection
        model_label = QLabel("AI MODEL")
        model_label.setObjectName("fieldLabel")
        settings_layout.addWidget(model_label)
        
        self.model_input = QComboBox()
        self.model_input.setEditable(False)
        
        # Models list
        self.models_data = {
            "Gemini 2.5 Flash (Рекомендуется)": "gemini-2.5-flash",
            "Gemini 2.5 Flash-Lite (Эконом)": "gemini-2.5-flash-lite",
            "Gemini 2.5 Pro (Профессиональная)": "gemini-2.5-pro",
            "Gemini 3.0 Pro Preview (Топ)": "gemini-3-pro-preview"
        }
        
        for display_name, model_id in self.models_data.items():
            self.model_input.addItem(display_name, model_id)
        
        self.model_input.currentIndexChanged.connect(self.update_model_description)
        settings_layout.addWidget(self.model_input)

        # Model Description Label
        self.model_desc_label = QLabel()
        self.model_desc_label.setObjectName("descLabel")
        self.model_desc_label.setWordWrap(True)
        self.model_desc_label.setOpenExternalLinks(True)
        self.model_desc_label.setStyleSheet("color: #b9bbbe; font-size: 12px; margin-top: 5px;")
        settings_layout.addWidget(self.model_desc_label)
        
        # Add stretch to settings layout
        settings_layout.addStretch()
        
        scroll_area.setWidget(settings_widget)
        layout.addWidget(scroll_area)
        
        # Save Button
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        # Status Section
        self.status_label = QLabel("READY")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Manual Controls
        self.record_btn = QPushButton("Start Recording")
        self.record_btn.setObjectName("recordButton")
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_btn)

    def apply_styles(self):
        self.setStyleSheet("""
            /* Main Window Background */
            QMainWindow {
                background-color: #36393f;
            }
            QWidget#centralWidget {
                background-color: #36393f;
            }
            
            /* Scroll Area */
            QScrollArea#settingsScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            
            /* Header */
            QLabel#headerLabel {
                color: #ffffff;
                font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            
            /* Settings Container */
            QWidget#settingsWidget {
                background-color: #2f3136;
                border-radius: 8px;
            }
            
            /* Field Labels */
            QLabel#fieldLabel {
                color: #b9bbbe;
                font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
                margin-top: 5px;
            }
            
            /* Inputs */
            QLineEdit, QComboBox, HotkeyInput {
                background-color: #202225;
                color: #dcddde;
                border: 1px solid #202225;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
                font-size: 14px;
            }
            QLineEdit:focus, QComboBox:focus, HotkeyInput:focus {
                border: 1px solid #00b0f4;
            }
            
            /* ComboBox Dropdown */
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #2f3136;
                color: #dcddde;
                border: 1px solid #202225;
                selection-background-color: #40444b;
            }
            
            /* Primary Button (Save) */
            QPushButton#primaryButton {
                background-color: #5865F2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#primaryButton:hover {
                background-color: #4752C4;
            }
            QPushButton#primaryButton:pressed {
                background-color: #3c45a5;
            }
            
            /* Record Button (Green/Red) */
            QPushButton#recordButton {
                background-color: #3ba55c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 12px;
                font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton#recordButton:hover {
                background-color: #2d7d46;
            }
            QPushButton#recordButton:checked {
                background-color: #ed4245;
            }
            
            /* Status Label */
            QLabel#statusLabel {
                color: #96989d;
                font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
                font-size: 13px;
                font-weight: bold;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                border: none;
                background: #2f3136;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #202225;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create a simple icon programmatically
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor(0, 120, 215)) # Blue
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        
        # Tray Menu
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def show_window(self):
        self.show()
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.activateWindow()

    def update_hotkey_listener(self):
        hotkey = self.hotkey_input.text().strip()
        if not hotkey:
            return

        try:
            if self.hotkey_manager:
                self.hotkey_manager.update_hotkey(hotkey)
            else:
                # Pass a lambda that emits the signal. 
                # The signal emission is thread-safe and will queue the slot execution on the main thread.
                self.hotkey_manager = self.HotkeyManagerClass(hotkey, self.hotkey_triggered.emit)
                self.hotkey_manager.start()
        except Exception as e:
            self.signals.error.emit(f"Failed to set hotkey '{hotkey}': {e}")
            # Fallback to a safe default if the user provided one fails
            if hotkey != "alt+1":
                print(f"Falling back to default hotkey: alt+1")
                self.hotkey_input.setText("alt+1")
                # Recursive call with default
                self.update_hotkey_listener()

    def update_model_description(self):
        model_id = self.model_input.currentData()
        desc = ""
        
        if model_id == "gemini-2.5-flash":
            desc = ("<b>Gemini 2.5 Flash (Баланс)</b><br>"
                    "Золотая середина для 90% задач. Если вам нужно продиктовать длинное письмо, заметку для блога или сообщение в мессенджер — это идеальный выбор. "
                    "Она достаточно умна, чтобы расставить знаки препинания и понять контекст, но при этом работает очень быстро. "
                    "В отличие от Lite версии, она лучше справляется со средней длиной текста и связной речью.<br>"
                    "<br><b>Цена:</b> ~$0.0015 / мин (~$0.09 / час)")
        elif model_id == "gemini-2.5-flash-lite":
             desc = ("<b>Gemini 2.5 Flash-Lite (Эконом)</b><br>"
                     "Специализированная модель для мгновенных команд. Используйте её для коротких фраз: 'поставь таймер на 10 минут', 'напомни купить молоко', 'следующий трек'. "
                     "В таких сценариях она работает быстрее всех и стоит в 3 раза дешевле обычной Flash. "
                     "Однако для диктовки текстов длиннее пары предложений она может упускать детали.<br>"
                     "<br><b>Цена:</b> ~$0.0005 / мин (~$0.03 / час)")
        elif model_id == "gemini-2.5-pro":
             desc = ("<b>Gemini 2.5 Pro (Интеллект)</b><br>"
                     "Модель для сложной работы с текстом. Используйте Pro, когда нужно не просто записать, а <b>преобразовать</b> речь. "
                     "Пример: вы диктуете сбивчивый поток мыслей, экаете и перескакиваете с темы на тему, а просите модель 'сделать красивый отчет'. "
                     "Flash запишет всё дословно с ошибками стиля, а Pro поймет суть, структурирует текст, выделит главное и оформит как документ. "
                     "Это ваш редактор, корректор и секретарь в одном флаконе.<br>"
                     "<br><b>Цена:</b> ~$0.0020 / мин (~$0.12 / час)")
        elif model_id == "gemini-3-pro-preview":
             desc = ("<b>Gemini 3.0 Pro Preview (Топ уровень)</b><br>"
                     "Самая передовая модель. Используйте её в тех редких случаях, когда даже 2.5 Pro не справляется. "
                     "Сложные логические цепочки, креативное написание текстов, работа с узкоспециализированной терминологией. "
                     "Это эксперимент, взгляд в будущее. Если задача требует максимального IQ от нейросети — выбирайте её. "
                     "Это самая дорогая модель в линейке.<br>"
                     "<br><b>Цена:</b> ~$0.0030 / мин (~$0.18 / час)")
        
        self.model_desc_label.setText(desc)

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        print("UI: start_recording called")
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self.signals.error.emit("Please enter an API Key first.")
            return

        self.is_recording = True
        hotkey = self.hotkey_input.text().strip()
        self.signals.status_update.emit(f"Recording... (Press {hotkey} to stop)")
        
        try:
            self.recorder.start_recording()
            self.record_btn.setText("Stop Recording (Manual)")
            # Show Overlay
            self.overlay.show_recording()
        except Exception as e:
            print(f"UI: Error starting recorder: {e}")
            self.signals.error.emit(f"Failed to start recording: {e}")
            self.is_recording = False

    def stop_recording(self):
        print("UI: stop_recording called")
        self.is_recording = False
        self.signals.status_update.emit("Processing...")
        
        try:
            audio_file, duration = self.recorder.stop_recording()
            print(f"UI: Audio saved to {audio_file}, duration: {duration:.2f}s")
            self.record_btn.setText("Start Recording")
            
            # Show Overlay Loading
            self.overlay.show_transcribing()
            
            if audio_file:
                # Start transcription in a separate thread
                threading.Thread(target=self.process_audio, args=(audio_file, duration)).start()
            else:
                print("UI: No audio file returned.")
                self.signals.error.emit("Recording failed (no audio file).")
                self.overlay.hide_overlay()
        except Exception as e:
            print(f"UI: Error stopping recorder: {e}")
            self.signals.error.emit(f"Failed to stop recording: {e}")
            self.overlay.hide_overlay()

    def process_audio(self, audio_file, duration):
        try:
            api_key = self.api_key_input.text().strip()
            model_id = self.model_input.currentData()
            
            if not model_id:
                 # Fallback
                model_id = "gemini-2.5-flash"

            # Calculate estimated cost
            cost_per_min = 0.0015 # Default Flash
            if "lite" in model_id:
                cost_per_min = 0.0005
            elif "2.5-pro" in model_id:
                cost_per_min = 0.0020
            elif "3-pro" in model_id:
                cost_per_min = 0.0030
            
            cost = (duration / 60.0) * cost_per_min
            if cost < 0.000001: cost = 0.0 
            
            transcriber = self.TranscriberClass(api_key, model_id)
            text = transcriber.transcribe(audio_file)
            self.signals.finished.emit(text, duration, cost)
        except Exception as e:
            self.signals.error.emit(str(e))

    def on_transcription_finished(self, text, duration, cost):
        self.update_status("Transcription complete. Pasting text...")
        print(f"Transcribed: {text}")
        
        try:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            self.overlay.show_success(f"{duration:.1f}s\n${cost:.6f}")
        except Exception as e:
            self.on_error(f"Paste failed: {e}")
            
        self.update_status("Ready")

    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")

    def on_error(self, message):
        if "400" in message or "location" in message.lower():
            message += "\n(Ошибка региона: Используйте VPN - США/Европа)"
        self.status_label.setText(f"Ошибка: {message}")
        self.overlay.hide_overlay()

    def save_settings(self):
        settings = {
            "api_key": self.api_key_input.text(),
            "hotkey": self.hotkey_input.text(),
            "model": self.model_input.currentData() 
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f)
        
        self.update_hotkey_listener()
        QMessageBox.information(self, "Settings", "Settings saved.")

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.api_key_input.setText(settings.get("api_key", ""))
                self.hotkey_input.setText(settings.get("hotkey", "alt+1"))
                
                model_id = settings.get("model", "gemini-2.5-flash")
                # Find by data
                index = self.model_input.findData(model_id)
                if index >= 0:
                    self.model_input.setCurrentIndex(index)
            
            # Update description initially
            self.update_model_description()
                    
        except (FileNotFoundError, json.JSONDecodeError):
            # Initial update if no settings
            self.update_model_description()
            pass

    def closeEvent(self, event):
        # Quit application on close
        self.quit_app()
        event.accept()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                # Minimize to tray
                event.ignore()
                self.hide()
                self.tray_icon.showMessage(
                    "Gemini Voice Writer",
                    "Application minimized to tray.",
                    QSystemTrayIcon.MessageIcon.Information,
                    1000
                )
        super().changeEvent(event)

    def quit_app(self):
        if self.hotkey_manager:
            self.hotkey_manager.stop()
        QApplication.quit()
