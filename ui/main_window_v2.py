"""Modern UI in WhisperTyping style with Gemini theme."""
import sys
import os
import json
import threading
import time
import wave
import tempfile
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QFrame,
    QListWidget, QListWidgetItem, QScrollArea, QApplication,
    QSystemTrayIcon, QMenu, QMessageBox, QSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QObject, QStandardPaths, QDateTime, QTimer, QMetaObject, Q_ARG
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
import shutil

import sounddevice as sd
import pyautogui
import pyperclip
import keyboard
import google.generativeai as genai

from ui.recording_widget import RecordingWidget
from utils.logger import get_logger
from utils.history_manager import HistoryManager, TranscriptionRecord
from core.chunked_transcriber import ChunkedTranscriber

# Initialize logger
log = get_logger()

# Cyrillic to Latin keyboard mapping (physical key positions on Russian keyboard)
# Uses keyboard library key names
CYRILLIC_TO_LATIN = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
    'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
    'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
    'б': ',', 'ю': '.', 'ё': '`',
    # Uppercase
    'Й': 'q', 'Ц': 'w', 'У': 'e', 'К': 'r', 'Е': 't', 'Н': 'y', 'Г': 'u', 'Ш': 'i', 'Щ': 'o', 'З': 'p',
    'Х': '[', 'Ъ': ']', 'Ф': 'a', 'Ы': 's', 'В': 'd', 'А': 'f', 'П': 'g', 'Р': 'h', 'О': 'j', 'Л': 'k',
    'Д': 'l', 'Ж': ';', 'Э': "'", 'Я': 'z', 'Ч': 'x', 'С': 'c', 'М': 'v', 'И': 'b', 'Т': 'n', 'Ь': 'm',
    'Б': ',', 'Ю': '.', 'Ё': '`',
}

# Scan code for grave/backtick key (`) - keyboard library doesn't support it by name
GRAVE_SCANCODE = 41

def convert_hotkey_cyrillic(hotkey: str) -> str:
    """Convert cyrillic characters in hotkey to their Latin equivalents."""
    parts = hotkey.lower().split('+')
    converted = []
    
    for part in parts:
        part = part.strip()
        if part in CYRILLIC_TO_LATIN:
            converted.append(CYRILLIC_TO_LATIN[part])
        else:
            converted.append(part)
    
    return '+'.join(converted)

def is_grave_hotkey(hotkey: str) -> bool:
    """Check if hotkey contains grave/backtick key."""
    lower = hotkey.lower()
    return '`' in lower or 'ё' in lower


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        base_path = sys._MEIPASS
    else:
        # Running as script
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class WorkerSignals(QObject):
    status_update = pyqtSignal(str)
    finished = pyqtSignal(str, float, float)
    retranscribe_finished = pyqtSignal(str, int)  # text, history_index
    error = pyqtSignal(str)
    audio_level = pyqtSignal(float)  # For waveform animation


class SidebarButton(QPushButton):
    """Styled sidebar navigation button."""
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self._update_text()
    
    def _update_text(self):
        self.setText(f"  {self._icon}  {self._text}")
    
    def setChecked(self, checked):
        super().setChecked(checked)
        self._update_text()


class MainWindowV2(QMainWindow):
    """Modern main window with sidebar navigation."""
    
    hotkey_triggered = pyqtSignal()
    
    COLORS = {
        'bg_dark': '#0f0f1a',
        'bg_sidebar': '#16162a', 
        'bg_content': '#1a1a2e',
        'bg_card': '#252540',
        'accent': '#8b5cf6',
        'accent_hover': '#a78bfa',
        'text': '#ffffff',
        'text_dim': '#9ca3af',
        'text_muted': '#6b7280',
        'border': '#374151',
        'success': '#22c55e',
        'error': '#ef4444',
    }
    
    def __init__(self, recorder, transcriber_class, hotkey_manager_class):
        super().__init__()
        self.recorder = recorder
        self.TranscriberClass = transcriber_class
        self.HotkeyManagerClass = hotkey_manager_class
        
        self.hotkey_manager = None
        self.is_recording = False
        
        self.stats = {
            'transcriptions': 0,
            'total_duration': 0,
            'total_chars': 0,
        }
        
        self.history = []
        self.history_enabled = True
        
        # Initialize history manager (SQLite database)
        self.history_manager = HistoryManager()
        log.info(f"History database initialized at: {self.history_manager.db_path}")
        
        self.setWindowTitle("Gemini Voice Writer")
        self.setGeometry(100, 100, 900, 650)
        self.setMinimumSize(800, 550)
        
        self._set_icon()
        
        # Recording widget (floating)
        self.recording_widget = RecordingWidget()
        self.recording_widget.recording_toggled.connect(self._toggle_recording)
        self.recording_widget.settings_requested.connect(self._show_settings)
        self.recording_widget.hide_to_tray_requested.connect(self._hide_all_windows)
        self.recording_widget.close_app_requested.connect(self._quit)
        self.recording_widget.show()
        
        self.signals = WorkerSignals()
        self.signals.status_update.connect(self._update_status)
        self.signals.finished.connect(self._on_transcription_finished)
        self.signals.retranscribe_finished.connect(self._on_retranscribe_finished)
        self.signals.error.connect(self._on_error)
        self.signals.audio_level.connect(self._on_audio_level)
        self.hotkey_triggered.connect(self._toggle_recording)
        
        self._setup_ui()
        self._apply_styles()
        self._init_tray()
        self._load_settings()
        self._init_hotkey()
    
    def _set_icon(self):
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 20)
        sidebar_layout.setSpacing(4)
        
        logo = QLabel("Gemini Voice Writer")
        logo.setObjectName("logo")
        sidebar_layout.addWidget(logo)
        sidebar_layout.addSpacing(20)
        
        self.nav_buttons = []
        nav_items = [
            ("\u2699", "Основные"),
            ("\U0001F3A4", "Транскрибация"),
            ("\u2328", "Активация"),
            ("\U0001F50A", "Звуки"),
            ("\U0001F4DC", "История"),
            ("\U0001F4CA", "Статистика"),
        ]
        
        for icon, text in nav_items:
            btn = SidebarButton(icon, text)
            btn.clicked.connect(lambda checked, t=text: self._switch_page(t))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append((text, btn))
        
        sidebar_layout.addStretch()
        
        version = QLabel("Gemini Voice Writer v2.0")
        version.setObjectName("version")
        sidebar_layout.addWidget(version)
        
        # Author info
        author_link = QLabel('<span style="color: #9ca3af;">Автор: </span><a href="https://t.me/Pavel_TeaGPT" style="color: #8b5cf6;">t.me/Pavel_TeaGPT</a>')
        author_link.setObjectName("authorLink")
        author_link.setOpenExternalLinks(True)
        author_link.setCursor(Qt.CursorShape.PointingHandCursor)
        sidebar_layout.addWidget(author_link)
        
        # Empty line as spacer
        spacer_label = QLabel("")
        spacer_label.setObjectName("authorLabel")
        sidebar_layout.addWidget(spacer_label)
        
        # P.S. line
        author_ps = QLabel("P.S: По сотрудничеству пишите в ЛС\n(Открыт к новым проектам)")
        author_ps.setObjectName("authorLabel")
        author_ps.setWordWrap(True)
        sidebar_layout.addWidget(author_ps)
        
        main_layout.addWidget(sidebar)
        
        content = QFrame()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Scroll area for pages content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("contentScroll")
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        
        self.pages = QStackedWidget()
        self._create_pages()
        scroll_layout.addWidget(self.pages)
        
        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area, 1)
        
        # Bottom buttons row (Save/Cancel) - hidden by default
        self.buttons_row = QWidget()
        self.buttons_row.setObjectName("buttonsRow")
        buttons_layout = QHBoxLayout(self.buttons_row)
        buttons_layout.setContentsMargins(30, 10, 30, 15)
        buttons_layout.addStretch()
        
        self.cancel_settings_btn = QPushButton("Отмена")
        self.cancel_settings_btn.setObjectName("smallButton")
        self.cancel_settings_btn.clicked.connect(self._cancel_settings_changes)
        buttons_layout.addWidget(self.cancel_settings_btn)
        
        self.save_settings_btn = QPushButton("Сохранить")
        self.save_settings_btn.setObjectName("primaryButton")
        self.save_settings_btn.setMinimumWidth(120)
        self.save_settings_btn.clicked.connect(self._save_and_close_settings)
        buttons_layout.addWidget(self.save_settings_btn)
        
        self.buttons_row.hide()  # Hidden until changes are made
        content_layout.addWidget(self.buttons_row)
        
        main_layout.addWidget(content, 1)
        
        self.nav_buttons[0][1].setChecked(True)
        
        # Track settings changes
        self._settings_changed = False
        self._original_settings = {}

    def _create_pages(self):
        self.pages.addWidget(self._create_general_page())
        self.pages.addWidget(self._create_transcription_page())
        self.pages.addWidget(self._create_activation_page())
        self.pages.addWidget(self._create_sounds_page())
        self.pages.addWidget(self._create_history_page())
        self.pages.addWidget(self._create_stats_page())
    
    def _create_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        if title:
            label = QLabel(title)
            label.setObjectName("cardTitle")
            layout.addWidget(label)
        
        return card, layout
    
    def _create_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        header = QLabel("Основные настройки")
        header.setObjectName("pageHeader")
        layout.addWidget(header)
        
        card, card_layout = self._create_card("Настройка API")
        
        api_label = QLabel("API ключ Gemini")
        api_label.setObjectName("fieldLabel")
        card_layout.addWidget(api_label)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Введите ваш API ключ Gemini...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setObjectName("input")
        card_layout.addWidget(self.api_key_input)
        
        # Proxy settings
        card_layout.addSpacing(10)
        proxy_label = QLabel("Proxy")
        proxy_label.setObjectName("fieldLabel")
        card_layout.addWidget(proxy_label)

        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.setObjectName("input")
        self.proxy_mode_combo.addItem("Встроенный", "built_in")
        self.proxy_mode_combo.addItem("Свой", "custom")
        card_layout.addWidget(self.proxy_mode_combo)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://login:password@ip:port")
        self.proxy_input.setObjectName("input")
        card_layout.addWidget(self.proxy_input)

        self.proxy_hint_label = QLabel("Встроенный proxy используется скрыто. Для своего proxy укажи полный URL.")
        self.proxy_hint_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        card_layout.addWidget(self.proxy_hint_label)

        layout.addWidget(card)
        
        self.save_btn = QPushButton("Сохранить настройки")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save_settings)
        layout.addWidget(self.save_btn)
        
        # Hidden status label (used for internal status updates)
        self.status_label = QLabel("")
        self.status_label.hide()
        
        # Hidden checkboxes for settings compatibility
        self.show_overlay_cb = QCheckBox()
        self.show_overlay_cb.setChecked(True)
        self.show_overlay_cb.hide()
        self.show_cost_cb = QCheckBox()
        self.show_cost_cb.setChecked(True)
        self.show_cost_cb.hide()
        
        layout.addStretch()
        return page
    
    def _create_transcription_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        header = QLabel("Настройки транскрибации")
        header.setObjectName("pageHeader")
        layout.addWidget(header)
        
        # Hidden method_combo for settings compatibility
        self.method_combo = QComboBox()
        self.method_combo.addItem("Standard API", "standard")
        self.method_combo.hide()
        
        # AI Model
        card, card_layout = self._create_card("Модель ИИ")
        
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("input")
        models = [
            ("Gemini 2.5 Flash (Рекомендуется)", "gemini-2.5-flash"),
            ("Gemini 3 Flash Preview", "gemini-3-flash-preview"),
            ("Gemini 3.1 Flash-Lite Preview", "gemini-3.1-flash-lite-preview"),
            ("Gemini 3.1 Pro Preview", "gemini-3.1-pro-preview"),
            ("Gemini 2.0 Flash (Быстрый)", "gemini-2.0-flash"),
            ("Gemini 2.0 Flash-Lite (Экономный)", "gemini-2.0-flash-lite"),
            ("Gemini 2.5 Pro (Профессиональный)", "gemini-2.5-pro"),
        ]
        for name, value in models:
            self.model_combo.addItem(name, value)
        card_layout.addWidget(self.model_combo)
        
        layout.addWidget(card)
        
        # Language selection
        card_lang, card_lang_layout = self._create_card("Язык транскрибации")
        
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("input")
        languages = [
            ("Русский", "Russian"),
            ("Английский", "English"),
            ("Немецкий", "German"),
            ("Французский", "French"),
            ("Испанский", "Spanish"),
            ("Итальянский", "Italian"),
            ("Китайский", "Chinese"),
            ("Японский", "Japanese"),
            ("Авто (определить)", "auto"),
        ]
        for name, value in languages:
            self.language_combo.addItem(name, value)
        card_lang_layout.addWidget(self.language_combo)
        
        lang_hint = QLabel("Технические термины и названия сохраняются на оригинальном языке")
        lang_hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        card_lang_layout.addWidget(lang_hint)
        
        layout.addWidget(card_lang)
        
        # Real-time display settings
        card2, card_layout2 = self._create_card("Отображение")
        
        self.show_realtime_text_cb = QCheckBox("Показывать текст в реальном времени")
        self.show_realtime_text_cb.setChecked(False)
        self.show_realtime_text_cb.setObjectName("checkbox")
        self.show_realtime_text_cb.setToolTip(
            "Когда включено, текст будет появляться в виджете по мере произнесения"
        )
        card_layout2.addWidget(self.show_realtime_text_cb)
        
        layout.addWidget(card2)
        
        self.record_btn = QPushButton("Начать запись")
        self.record_btn.setObjectName("recordButton")
        self.record_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self.record_btn)
        
        layout.addStretch()
        return page
    
    def _create_activation_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        header = QLabel("Активация клавишами")
        header.setObjectName("pageHeader")
        layout.addWidget(header)
        
        # Hotkey settings card
        card, card_layout = self._create_card("Настройка горячих клавиш")
        card_layout.setSpacing(12)
        
        from ui.custom_widgets import HotkeyInput
        
        # Start/Stop recording hotkey
        hotkey_label = QLabel("Начать/Остановить запись:")
        hotkey_label.setObjectName("fieldLabel")
        card_layout.addWidget(hotkey_label)
        
        self.hotkey_input = HotkeyInput()
        self.hotkey_input.setObjectName("input")
        self.hotkey_input.setText("alt+ё")
        self.hotkey_input.setMinimumHeight(44)
        self.hotkey_input.textChanged.connect(self._on_hotkey_changed)
        card_layout.addWidget(self.hotkey_input)
        
        card_layout.addSpacing(8)
        
        # Cancel recording hotkey
        cancel_label = QLabel("Отменить запись:")
        cancel_label.setObjectName("fieldLabel")
        card_layout.addWidget(cancel_label)
        
        self.cancel_hotkey_input = HotkeyInput()
        self.cancel_hotkey_input.setObjectName("input")
        self.cancel_hotkey_input.setText("alt+1")
        self.cancel_hotkey_input.setMinimumHeight(44)
        self.cancel_hotkey_input.textChanged.connect(self._on_cancel_hotkey_changed)
        card_layout.addWidget(self.cancel_hotkey_input)
        
        layout.addWidget(card)
        
        # Output settings card
        card2, card_layout2 = self._create_card("Вывод")
        card_layout2.setSpacing(12)
        
        self.auto_paste_cb = QCheckBox("Автовставка в активное текстовое поле")
        self.auto_paste_cb.setChecked(True)
        self.auto_paste_cb.setObjectName("checkbox")
        card_layout2.addWidget(self.auto_paste_cb)
        
        self.auto_copy_cb = QCheckBox("Автокопирование в буфер обмена")
        self.auto_copy_cb.setChecked(True)
        self.auto_copy_cb.setObjectName("checkbox")
        card_layout2.addWidget(self.auto_copy_cb)
        
        layout.addWidget(card2)
        
        # Widget visibility settings card
        card3, card_layout3 = self._create_card("Виджет записи")
        
        self.show_widget_on_record_cb = QCheckBox("Показывать виджет при начале записи")
        self.show_widget_on_record_cb.setChecked(False)
        self.show_widget_on_record_cb.setObjectName("checkbox")
        self.show_widget_on_record_cb.setToolTip(
            "Когда включено, виджет записи появится на экране при начале записи "
            "и автоматически скроется через 3 секунды после завершения транскрибации"
        )
        card_layout3.addWidget(self.show_widget_on_record_cb)
        
        layout.addWidget(card3)
        
        layout.addStretch()
        return page
    
    def _create_sounds_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        header = QLabel("Звуковые эффекты")
        header.setObjectName("pageHeader")
        layout.addWidget(header)
        
        card, card_layout = self._create_card("Звук уведомления")
        
        self.sound_enabled_cb = QCheckBox("Включить звуковую обратную связь")
        self.sound_enabled_cb.setChecked(True)
        self.sound_enabled_cb.setObjectName("checkbox")
        card_layout.addWidget(self.sound_enabled_cb)
        
        sound_row = QHBoxLayout()
        self.sound_combo = QComboBox()
        self.sound_combo.setObjectName("input")
        sounds = [
            ("Затвор камеры", "01_camera_shutter"),
            ("Механический клик", "02_mechanical_click"),
            ("Переключатель", "03_switch_toggle"),
            ("Взвод курка", "04_gun_cock"),
            ("Печатная машинка", "05_typewriter"),
            ("Щелчок", "06_snap"),
            ("Поп", "07_pop"),
            ("Выключатель", "08_light_switch"),
            ("Клик мыши", "09_mouse_click"),
            ("Клик ручки", "10_pen_click"),
            ("Защёлка двери", "11_door_latch"),
            ("Зажигалка", "12_zippo"),
        ]
        for name, value in sounds:
            self.sound_combo.addItem(name, value)
        sound_row.addWidget(self.sound_combo, 1)
        
        play_btn = QPushButton("Играть")
        play_btn.setFixedWidth(70)
        play_btn.setObjectName("smallButton")
        play_btn.clicked.connect(self._play_sound)
        sound_row.addWidget(play_btn)
        
        card_layout.addLayout(sound_row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _create_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        header_row = QHBoxLayout()
        header = QLabel("История")
        header.setObjectName("pageHeader")
        header_row.addWidget(header)
        header_row.addStretch()
        
        self.history_count_label = QLabel("(0)")
        self.history_count_label.setObjectName("fieldLabel")
        header_row.addWidget(self.history_count_label)
        
        delete_btn = QPushButton("Удалить историю")
        delete_btn.setObjectName("smallButton")
        delete_btn.clicked.connect(self._clear_history)
        header_row.addWidget(delete_btn)
        
        layout.addLayout(header_row)
        
        subtitle = QLabel("Ваши аудио и транскрибации хранятся исключительно на вашем устройстве")
        subtitle.setObjectName("fieldLabel")
        layout.addWidget(subtitle)
        
        card, card_layout = self._create_card("")
        self.history_enabled_cb = QCheckBox("История включена")
        self.history_enabled_cb.setChecked(True)
        self.history_enabled_cb.setObjectName("checkbox")
        self.history_enabled_cb.stateChanged.connect(self._on_history_toggle)
        card_layout.addWidget(self.history_enabled_cb)
        layout.addWidget(card)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("historyScroll")
        
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setSpacing(10)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.addStretch()
        
        scroll.setWidget(self.history_container)
        layout.addWidget(scroll, 1)
        
        return page
    
    def _create_history_item(self, item: dict, index: int) -> QFrame:
        """Create history item card like WhisperTyping style."""
        card = QFrame()
        card.setObjectName("historyCard")
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)
        
        # Top row: time, duration and action buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        
        # Time label
        time_label = QLabel(item.get('time', 'Unknown'))
        time_label.setObjectName("historyTime")
        top_row.addWidget(time_label)
        
        # Duration with separator
        duration = item.get('duration', 0)
        duration_label = QLabel(f"| {duration:.1f}s")
        duration_label.setObjectName("historyDuration")
        top_row.addWidget(duration_label)
        
        top_row.addStretch()
        
        # Action buttons (horizontal, like WhisperTyping)
        audio_file = item.get('audio_file')
        
        # Play button (only if audio exists)
        if audio_file and os.path.exists(audio_file):
            play_btn = QPushButton("▶")
            play_btn.setFixedSize(28, 28)
            play_btn.setObjectName("historyActionBtn")
            play_btn.setToolTip("Воспроизвести запись")
            play_btn.clicked.connect(lambda checked, f=audio_file: self._play_history_audio(f))
            top_row.addWidget(play_btn)
            
            # Re-transcribe button
            retrans_btn = QPushButton("↻")
            retrans_btn.setFixedSize(28, 28)
            retrans_btn.setObjectName("historyActionBtn")
            retrans_btn.setToolTip("Перетранскрибировать")
            retrans_btn.clicked.connect(lambda checked, f=audio_file, i=index: self._retranscribe_audio(f, i))
            top_row.addWidget(retrans_btn)
        
        # Copy button
        text = item.get('text', '')
        copy_btn = QPushButton("📋")
        copy_btn.setFixedSize(28, 28)
        copy_btn.setObjectName("historyActionBtn")
        copy_btn.setToolTip("Копировать в буфер")
        copy_btn.clicked.connect(lambda checked, t=text: self._copy_history_item(t))
        top_row.addWidget(copy_btn)
        
        # Delete button
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(28, 28)
        delete_btn.setObjectName("historyActionBtn")
        delete_btn.setToolTip("Удалить")
        delete_btn.clicked.connect(lambda checked, i=index: self._delete_history_item(i))
        top_row.addWidget(delete_btn)
        
        main_layout.addLayout(top_row)
        
        # Text content below
        text_label = QLabel(text[:300] + ('...' if len(text) > 300 else ''))
        text_label.setObjectName("historyText")
        text_label.setWordWrap(True)
        main_layout.addWidget(text_label)
        
        return card
    
    def _copy_history_item(self, text: str):
        pyperclip.copy(text)
        self.status_label.setText("Скопировано в буфер!")
    
    def _play_history_audio(self, audio_file: str):
        """Play audio file from history."""
        if not audio_file or not os.path.exists(audio_file):
            self.status_label.setText("Аудиофайл не найден!")
            return
        
        try:
            # Open with system default player
            import subprocess
            if sys.platform == 'win32':
                os.startfile(audio_file)
            elif sys.platform == 'darwin':
                subprocess.run(['open', audio_file])
            else:
                subprocess.run(['xdg-open', audio_file])
            self.status_label.setText("Воспроизведение...")
        except Exception as e:
            print(f"Play error: {e}")
            self.status_label.setText(f"Ошибка воспроизведения: {str(e)[:30]}")
    
    def _retranscribe_audio(self, audio_file: str, history_index: int):
        """Re-transcribe audio file and update history item."""
        if not audio_file or not os.path.exists(audio_file):
            self.status_label.setText("Аудиофайл не найден!")
            return
        
        if not self.api_key_input.text().strip():
            self.status_label.setText("Сначала введите API ключ!")
            return
        
        self.status_label.setText("Перетранскрибация...")
        self.recording_widget.set_processing()
        self._transcription_start_time = time.time()
        
        # Get duration from history (more reliable than parsing file)
        duration = self.history[history_index].get('duration', 0)
        
        # Run re-transcription in background
        threading.Thread(
            target=self._do_retranscribe,
            args=(audio_file, duration, history_index),
            daemon=True
        ).start()
    
    def _do_retranscribe(self, audio_file: str, duration: float, history_index: int):
        """Background re-transcription using REST API."""
        try:
            import base64
            import requests
            
            api_key = self.api_key_input.text().strip()
            model = self.model_combo.currentData() or "gemini-2.5-flash"
            
            log.info(f"[RETRANSCRIBE] Starting: {audio_file}")
            log.info(f"[RETRANSCRIBE] Model: {model}")
            
            with open(audio_file, 'rb') as f:
                audio_bytes = f.read()
            
            log.debug(f"[RETRANSCRIBE] File size: {len(audio_bytes)/1024:.1f} KB")
            
            mime_type = "audio/flac" if audio_file.endswith('.flac') else "audio/wav"
            
            # REST API request (bypasses SDK regional restrictions)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Transcribe this audio exactly as spoken. Use Cyrillic for Russian words and Latin script for English technical terms, brand names, acronyms, and anglicisms. Do not transliterate English terms into Cyrillic. Normalize keyboard shortcuts in the form 'Ctrl + Shift + V', 'Alt + 1', 'Ctrl + C'. Add natural punctuation and capitalization. Return ONLY the final transcribed text."},
                        {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(audio_bytes).decode('utf-8')}}
                    ]
                }]
            }
            
            log.debug("[RETRANSCRIBE] Sending to REST API...")
            t0 = time.time()
            
            # Proxy support
            proxies = None
            proxy_url = self._get_effective_proxy()
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}
            
            response = requests.post(url, json=payload, timeout=60, proxies=proxies)
            
            t1 = time.time()
            print(f"[RETRANSCRIBE] API response in {t1-t0:.2f}s, status={response.status_code}")
            
            if response.status_code != 200:
                error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
                raise Exception(f"API error {response.status_code}: {error_msg}")
            
            result = response.json()
            text = ""
            if "candidates" in result and result["candidates"]:
                candidate = result["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    text = candidate["content"]["parts"][0].get("text", "").strip()
            
            print(f"[RETRANSCRIBE] Result: '{text[:100]}...'")
            
            # Emit signal to update UI in main thread (history update happens there)
            self.signals.retranscribe_finished.emit(text, history_index)
            
            print(f"[RETRANSCRIBE] Complete!")
            
        except Exception as e:
            print(f"[RETRANSCRIBE] Error: {e}")
            import traceback
            traceback.print_exc()
            self.signals.error.emit(f"Re-transcribe error: {str(e)[:40]}")
    
    def _delete_history_item(self, index: int):
        """Delete a single history item by index."""
        if 0 <= index < len(self.history):
            item = self.history[index]
            record_id = item.get('id')
            
            # Delete from database
            if record_id:
                try:
                    self.history_manager.delete(record_id)
                    log.info(f"Deleted record {record_id} from database")
                except Exception as e:
                    log.error(f"Failed to delete from database: {e}")
            
            # Delete audio file
            audio_file = item.get('audio_file')
            if audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                    log.debug(f"Deleted audio file: {audio_file}")
                except Exception as e:
                    log.warning(f"Failed to delete audio file: {e}")
            
            self.history.pop(index)
            self._recalculate_stats_from_history()
            self._update_history_display()
            self._save_settings()
            self.status_label.setText("Запись удалена!")
    
    def _on_retranscribe_finished(self, text: str, history_index: int):
        """Called when re-transcription is complete."""
        log.info(f"Re-transcription complete for index {history_index}")
        
        # Update history item text
        if 0 <= history_index < len(self.history):
            item = self.history[history_index]
            item['text'] = text
            item['time'] = QDateTime.currentDateTime().toString("hh:mm | dd.MM.yyyy") + " (re-transcribed)"
            
            # Update in database if record has ID
            record_id = item.get('id')
            if record_id:
                try:
                    # Update text in database
                    conn = self.history_manager._get_connection()
                    conn.execute(
                        "UPDATE transcriptions SET text = ?, timestamp = ? WHERE id = ?",
                        (text, QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate), record_id)
                    )
                    conn.commit()
                    log.info(f"Updated record {record_id} in database")
                except Exception as e:
                    log.error(f"Failed to update database: {e}")
        
        transcription_time = time.time() - getattr(self, '_transcription_start_time', time.time())
        self.recording_widget.set_success(transcription_time)
        self._update_history_display()
        self._save_settings()
        self.status_label.setText("Перетранскрибация завершена!")
        
        # Copy new text to clipboard
        pyperclip.copy(text)
    
    def _get_recordings_dir(self) -> str:
        """Get directory for storing audio recordings."""
        from utils.paths import get_recordings_dir
        return get_recordings_dir()
    
    def _add_to_history(self, text: str, duration: float, audio_file: str = None):
        if not self.history_enabled:
            log.debug("History disabled, skipping")
            return
        
        log.info(f"Adding to history: {len(text)} chars, {duration:.1f}s, audio: {audio_file}")
        
        # Save audio file to permanent location
        saved_audio_path = None
        if audio_file and os.path.exists(audio_file):
            try:
                recordings_dir = self._get_recordings_dir()
                timestamp = int(time.time() * 1000)
                ext = os.path.splitext(audio_file)[1] or '.wav'
                saved_filename = f"recording_{timestamp}{ext}"
                saved_audio_path = os.path.join(recordings_dir, saved_filename)
                shutil.copy2(audio_file, saved_audio_path)
                log.debug(f"Saved audio to: {saved_audio_path}")
            except Exception as e:
                log.error(f"Failed to save audio: {e}")
                saved_audio_path = None
        else:
            log.debug(f"No audio file to save (file: {audio_file})")
        
        # Save to SQLite database
        try:
            model = self.model_combo.currentData() or "gemini-2.5-flash"
            record = TranscriptionRecord(
                text=text,
                duration=duration,
                provider="gemini",
                model=model,
                cost=0.0,
                audio_path=saved_audio_path
            )
            record_id = self.history_manager.add(record)
            log.info(f"Saved to database with ID: {record_id}")
        except Exception as e:
            log.error(f"Failed to save to database: {e}")
        
        # Also keep in memory for UI display
        item = {
            'text': text,
            'duration': duration,
            'time': QDateTime.currentDateTime().toString("hh:mm | dd.MM.yyyy"),
            'timestamp': time.time(),
            'audio_file': saved_audio_path
        }
        self.history.insert(0, item)
        
        if len(self.history) > 100:
            self.history = self.history[:100]
        
        self._update_history_display()
    
    def _update_history_display(self):
        while self.history_layout.count() > 1:
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for index, item in enumerate(self.history):
            card = self._create_history_item(item, index)
            self.history_layout.insertWidget(self.history_layout.count() - 1, card)
        
        self.history_count_label.setText(f"({len(self.history)})")
    
    def _clear_history(self):
        """Clear all history from database and memory."""
        log.info("Clearing all history")
        
        # Delete audio files
        for item in self.history:
            audio_file = item.get('audio_file')
            if audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except Exception as e:
                    log.warning(f"Failed to delete audio file: {e}")
        
        # Clear database - delete all records
        try:
            conn = self.history_manager._get_connection()
            conn.execute("DELETE FROM transcriptions")
            conn.commit()
            log.info("Database cleared")
        except Exception as e:
            log.error(f"Failed to clear database: {e}")
        
        self.history = []
        self._recalculate_stats_from_history()
        self._update_history_display()
        self._save_settings()
        self.status_label.setText("История очищена!")
    
    def _recalculate_stats_from_history(self):
        """Recalculate stats based on current history."""
        self.stats = {
            'transcriptions': len(self.history),
            'total_duration': sum(item.get('duration', 0) for item in self.history),
            'total_chars': sum(len(item.get('text', '')) for item in self.history),
        }
        self._update_stats_display()
    
    def _on_history_toggle(self, state):
        self.history_enabled = state == Qt.CheckState.Checked.value
        if getattr(self, '_signals_connected', False):
            self._on_setting_changed()
    
    def _create_stats_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        header = QLabel("Ваша статистика")
        header.setObjectName("pageHeader")
        layout.addWidget(header)
        
        stats_row = QHBoxLayout()
        stats_row.setSpacing(15)
        
        card1, layout1 = self._create_card("")
        self.stat_count = QLabel("0")
        self.stat_count.setObjectName("statNumber")
        layout1.addWidget(self.stat_count, alignment=Qt.AlignmentFlag.AlignCenter)
        label1 = QLabel("Транскрибаций")
        label1.setObjectName("statLabel")
        layout1.addWidget(label1, alignment=Qt.AlignmentFlag.AlignCenter)
        stats_row.addWidget(card1)
        
        card2, layout2 = self._create_card("")
        self.stat_duration = QLabel("0м 0с")
        self.stat_duration.setObjectName("statNumber")
        layout2.addWidget(self.stat_duration, alignment=Qt.AlignmentFlag.AlignCenter)
        label2 = QLabel("Общая длительность")
        label2.setObjectName("statLabel")
        layout2.addWidget(label2, alignment=Qt.AlignmentFlag.AlignCenter)
        stats_row.addWidget(card2)
        
        card3, layout3 = self._create_card("")
        self.stat_chars = QLabel("0")
        self.stat_chars.setObjectName("statNumber")
        layout3.addWidget(self.stat_chars, alignment=Qt.AlignmentFlag.AlignCenter)
        label3 = QLabel("Всего символов")
        label3.setObjectName("statLabel")
        layout3.addWidget(label3, alignment=Qt.AlignmentFlag.AlignCenter)
        stats_row.addWidget(card3)
        
        layout.addLayout(stats_row)
        layout.addStretch()
        return page
    
    def _switch_page(self, page_name: str):
        pages = ["Основные", "Транскрибация", "Активация", "Звуки", "История", "Статистика"]
        idx = pages.index(page_name) if page_name in pages else 0
        self.pages.setCurrentIndex(idx)
        
        for name, btn in self.nav_buttons:
            btn.setChecked(name == page_name)

    def _apply_styles(self):
        # Get path to checkmark SVG
        checkmark_path = get_resource_path("ui/checkmark.svg").replace("\\", "/")
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {self.COLORS['bg_dark']}; }}
            
            #sidebar {{ background-color: {self.COLORS['bg_sidebar']}; border-right: 1px solid {self.COLORS['border']}; }}
            #content {{ background-color: {self.COLORS['bg_content']}; }}
            
            #logo {{ color: {self.COLORS['accent']}; font-size: 16px; font-weight: bold; padding: 10px 0; }}
            #version {{ color: {self.COLORS['text_muted']}; font-size: 11px; margin: 0; padding: 0; }}
            #authorLink {{ color: {self.COLORS['text_muted']}; font-size: 11px; margin: 0; padding: 0; }}
            #authorLabel {{ color: {self.COLORS['text_muted']}; font-size: 11px; margin: 0; padding: 0; }}
            
            SidebarButton {{
                background-color: transparent;
                color: {self.COLORS['text_dim']};
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 12px;
                font-size: 14px;
            }}
            SidebarButton:hover {{ background-color: {self.COLORS['bg_card']}; color: {self.COLORS['text']}; }}
            SidebarButton:checked {{ background-color: {self.COLORS['accent']}; color: white; font-weight: bold; }}
            
            #pageHeader {{ color: {self.COLORS['text']}; font-size: 24px; font-weight: bold; margin-bottom: 10px; }}
            
            #card {{ background-color: {self.COLORS['bg_card']}; border-radius: 12px; }}
            #cardTitle {{ color: {self.COLORS['text']}; font-size: 16px; font-weight: 600; }}
            #fieldLabel {{ color: {self.COLORS['text_dim']}; font-size: 13px; }}
            
            #input, QComboBox {{
                background-color: {self.COLORS['bg_content']};
                color: {self.COLORS['text']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                min-height: 20px;
            }}
            #input:focus, QComboBox:focus {{ border-color: {self.COLORS['accent']}; }}
            
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox QAbstractItemView {{
                background-color: {self.COLORS['bg_card']};
                color: {self.COLORS['text']};
                selection-background-color: {self.COLORS['accent']};
            }}
            
            #checkbox {{ color: {self.COLORS['text']}; font-size: 14px; spacing: 10px; }}
            #checkbox::indicator {{ width: 20px; height: 20px; border-radius: 4px; border: 2px solid {self.COLORS['border']}; background-color: transparent; }}
            #checkbox::indicator:checked {{ background-color: {self.COLORS['accent']}; border-color: {self.COLORS['accent']}; image: url({checkmark_path}); }}
            
            #primaryButton {{
                background-color: {self.COLORS['accent']};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 14px 24px;
                font-size: 15px;
                font-weight: bold;
            }}
            #primaryButton:hover {{ background-color: {self.COLORS['accent_hover']}; }}
            
            #recordButton {{
                background-color: {self.COLORS['success']};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 16px 24px;
                font-size: 16px;
                font-weight: bold;
            }}
            #recordButton:hover {{ background-color: #16a34a; }}
            
            #smallButton {{
                background-color: {self.COLORS['bg_content']};
                color: {self.COLORS['text']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            #smallButton:hover {{ background-color: {self.COLORS['accent']}; }}
            
            #status {{ color: {self.COLORS['text_dim']}; font-size: 13px; }}
            
            #statNumber {{ color: {self.COLORS['accent']}; font-size: 36px; font-weight: bold; }}
            #statLabel {{ color: {self.COLORS['text_dim']}; font-size: 13px; }}
            
            QScrollBar:vertical {{ width: 8px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {self.COLORS['border']}; border-radius: 4px; }}
            
            #historyScroll {{ background: transparent; border: none; }}
            #historyCard {{ background-color: {self.COLORS['bg_card']}; border-radius: 12px; border: 1px solid {self.COLORS['border']}; }}
            #historyCard:hover {{ border-color: {self.COLORS['accent']}; }}
            #historyTime {{ color: {self.COLORS['text_muted']}; font-size: 12px; }}
            #historyDuration {{ color: {self.COLORS['text_muted']}; font-size: 12px; }}
            #historyText {{ color: {self.COLORS['text']}; font-size: 13px; line-height: 1.4; margin-top: 4px; }}
            #historyActionBtn {{ 
                background: transparent; 
                border: 1px solid {self.COLORS['border']}; 
                border-radius: 6px; 
                font-size: 13px;
                color: {self.COLORS['text_dim']};
            }}
            #historyActionBtn:hover {{ background-color: {self.COLORS['bg_content']}; border-color: {self.COLORS['accent']}; color: {self.COLORS['text']}; }}
            
            #contentScroll {{ background: transparent; border: none; }}
            #contentScroll > QWidget > QWidget {{ background: transparent; }}
            #buttonsRow {{ background-color: {self.COLORS['bg_content']}; border-top: 1px solid {self.COLORS['border']}; }}
        """)
    
    def _init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.windowIcon())
        self.tray.setToolTip("Gemini Voice Writer")
        menu = QMenu()
        menu.addAction("Показать виджет", self._show_recording_widget)
        menu.addAction("Скрыть всё", self._hide_all_windows)
        menu.addAction("Настройки", self._show_settings)
        menu.addSeparator()
        menu.addAction("Выход", self._quit)
        self.tray.setContextMenu(menu)
        # При клике на иконку — показываем плашку записи
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        
        # Connect recording widget tray text signal
        self.recording_widget.tray_text_changed.connect(self._update_tray_tooltip)
    
    def _update_tray_tooltip(self, text: str):
        """Update tray icon tooltip with recording/processing status."""
        self.tray.setToolTip(text)
    
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Toggle widget visibility
            if self.recording_widget.isVisible():
                self._hide_all_windows()
            else:
                self._show_recording_widget()
    
    def _hide_all_windows(self):
        """Hide both main window and recording widget (minimize to tray)."""
        self.hide()
        self.recording_widget.hide()
        self.tray.setToolTip("Gemini Voice Writer (скрыто)")
    
    def _show_recording_widget(self):
        """Show the floating recording widget."""
        self.recording_widget.show()
        self.recording_widget.raise_()
        self.tray.setToolTip("Gemini Voice Writer")
    
    def _init_hotkey(self):
        self._registered_hotkeys = []
        self._setup_hotkeys()
        # Watchdog отключён — если клавиши перестанут работать, перезапустите приложение
    
    def _setup_hotkeys(self):
        """Setup all hotkeys."""
        # Remove old hotkeys
        for hk in getattr(self, '_registered_hotkeys', []):
            try:
                keyboard.remove_hotkey(hk)
            except:
                pass
        self._registered_hotkeys = []
        
        # Unhook all keyboard hooks and re-register (более надёжный способ)
        try:
            keyboard.unhook_all_hotkeys()
        except:
            pass
        
        # Main hotkey (start/stop recording)
        hotkey_raw = self.hotkey_input.text().strip() or "alt+1"
        
        if is_grave_hotkey(hotkey_raw):
            # Special handling for grave/backtick key using low-level hook
            self._setup_grave_hotkey('main')
            log.info(f"Main hotkey registered (grave hook): {hotkey_raw}")
        else:
            hotkey = convert_hotkey_cyrillic(hotkey_raw)
            try:
                hk = keyboard.add_hotkey(hotkey, self.hotkey_triggered.emit, suppress=False, trigger_on_release=False)
                self._registered_hotkeys.append(hk)
                log.info(f"Main hotkey registered: {hotkey_raw} -> {hotkey}")
            except Exception as e:
                log.error(f"Failed to set hotkey {hotkey_raw}: {e}")
        
        # Cancel hotkey (discard recording)
        cancel_hotkey_raw = self.cancel_hotkey_input.text().strip() or "alt+1"
        
        if is_grave_hotkey(cancel_hotkey_raw):
            self._setup_grave_hotkey('cancel')
            log.info(f"Cancel hotkey registered (grave hook): {cancel_hotkey_raw}")
        else:
            cancel_hotkey = convert_hotkey_cyrillic(cancel_hotkey_raw)
            try:
                hk = keyboard.add_hotkey(cancel_hotkey, self._cancel_recording, suppress=False, trigger_on_release=False)
                self._registered_hotkeys.append(hk)
                log.info(f"Cancel hotkey registered: {cancel_hotkey_raw} -> {cancel_hotkey}")
            except Exception as e:
                log.error(f"Failed to set cancel hotkey {cancel_hotkey_raw}: {e}")
    
    def _setup_grave_hotkey(self, hotkey_type: str):
        """Setup hotkey for grave/backtick key using low-level hook."""
        # Remove existing grave hook if any
        if hasattr(self, '_grave_hook') and self._grave_hook:
            try:
                keyboard.unhook(self._grave_hook)
            except:
                pass
            self._grave_hook = None
        
        def on_key_event(event):
            # Filter: only grave key (scan code 41) on key down
            if event.scan_code != GRAVE_SCANCODE:
                return
            if event.event_type != 'down':
                return
            
            # Only trigger if Alt is held
            if not keyboard.is_pressed('alt'):
                return
            
            # Debounce - 1 second between triggers
            current_time = time.time()
            last_grave = getattr(self, '_last_grave_time', 0)
            if current_time - last_grave < 1.0:
                return
            self._last_grave_time = current_time
            
            log.info(f"[GRAVE] Alt+` triggered, type={hotkey_type}")
            
            if hotkey_type == 'main':
                # Thread-safe call to main thread
                QMetaObject.invokeMethod(self, "_toggle_recording", Qt.ConnectionType.QueuedConnection)
            elif hotkey_type == 'cancel':
                QMetaObject.invokeMethod(self, "_cancel_recording", Qt.ConnectionType.QueuedConnection)
        
        # Use keyboard.hook to catch all events
        self._grave_hook = keyboard.hook(on_key_event)
        self._grave_hotkey_type = hotkey_type
    
    def _on_hotkey_changed(self):
        new_hotkey = self.hotkey_input.text().strip()
        if not new_hotkey:
            return
        self._setup_hotkeys()
        # Only save if signals are connected (not during initial load)
        if getattr(self, '_signals_connected', False):
            self._on_setting_changed()
        self.status_label.setText(f"Горячая клавиша: {new_hotkey}")
    
    def _on_cancel_hotkey_changed(self):
        new_hotkey = self.cancel_hotkey_input.text().strip()
        if not new_hotkey:
            return
        self._setup_hotkeys()
        # Only save if signals are connected (not during initial load)
        if getattr(self, '_signals_connected', False):
            self._on_setting_changed()
        self.status_label.setText(f"Клавиша отмены: {new_hotkey}")
    
    def _get_settings_path(self):
        from utils.paths import get_settings_path
        return get_settings_path()

    def _get_internal_proxy_path(self):
        settings_path = self._get_settings_path()
        return os.path.join(os.path.dirname(settings_path), "internal_proxy.json")

    def _load_internal_proxy(self):
        path = self._get_internal_proxy_path()
        if not os.path.exists(path):
            return ""
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            return (data.get("proxy") or "").strip()
        except Exception as e:
            log.warning(f"Failed to load internal proxy config: {e}")
            return ""

    def _save_internal_proxy(self, proxy_value):
        path = self._get_internal_proxy_path()
        try:
            with open(path, "w", encoding='utf-8') as f:
                json.dump({"proxy": (proxy_value or "").strip()}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f"Failed to save internal proxy config: {e}")

    def _get_selected_proxy_mode(self):
        if not hasattr(self, 'proxy_mode_combo'):
            return "custom"
        return self.proxy_mode_combo.currentData() or "custom"

    def _get_effective_proxy(self):
        mode = self._get_selected_proxy_mode()
        if mode == "built_in":
            proxy_value = self._load_internal_proxy()
            return proxy_value or None
        proxy_value = self.proxy_input.text().strip()
        return proxy_value or None

    def _update_proxy_ui(self):
        mode = self._get_selected_proxy_mode()
        is_custom = mode == "custom"
        self.proxy_input.setVisible(is_custom)
        self.proxy_input.setEnabled(is_custom)
        if hasattr(self, 'proxy_hint_label'):
            if is_custom:
                self.proxy_hint_label.setText("Укажи свой proxy в формате http://login:password@ip:port")
            else:
                self.proxy_hint_label.setText("Встроенный proxy активен. Его данные скрыты.")
    
    def _save_settings(self):
        # Note: history is now stored in SQLite database, not in JSON
        settings = {
            "api_key": self.api_key_input.text(),
            "proxy_mode": self._get_selected_proxy_mode(),
            "custom_proxy": self.proxy_input.text().strip(),
            "proxy": self.proxy_input.text().strip(),
            "hotkey": self.hotkey_input.text(),
            "cancel_hotkey": self.cancel_hotkey_input.text(),
            "auto_paste": self.auto_paste_cb.isChecked(),
            "auto_copy": self.auto_copy_cb.isChecked(),
            "model": self.model_combo.currentData(),
            "model_index": self.model_combo.currentIndex(),
            "language": self.language_combo.currentData(),
            "language_index": self.language_combo.currentIndex(),
            "method": self.method_combo.currentData() if hasattr(self, 'method_combo') else "live",
            "show_overlay": self.show_overlay_cb.isChecked(),
            "show_cost": self.show_cost_cb.isChecked(),
            "sound": self.sound_combo.currentData(),
            "sound_index": self.sound_combo.currentIndex(),
            "sound_enabled": self.sound_enabled_cb.isChecked(),
            "show_widget_on_record": self.show_widget_on_record_cb.isChecked(),
            "show_realtime_text": self.show_realtime_text_cb.isChecked(),
            "stats": self.stats,
            "history_enabled": self.history_enabled,
        }
        with open(self._get_settings_path(), "w", encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        self.status_label.setText("Настройки сохранены!")
        self._settings_changed = False
        self.buttons_row.hide()
        log.info(f"Settings saved. Model: {self.model_combo.currentData()}")
    
    def _save_and_close_settings(self):
        """Save settings with visual feedback."""
        # Visual feedback - change button text and color
        original_text = self.save_settings_btn.text()
        self.save_settings_btn.setText("✓ Сохранено!")
        self.save_settings_btn.setStyleSheet(f"background-color: {self.COLORS['success']}; color: white;")
        self.save_settings_btn.setEnabled(False)
        
        # Save settings
        self._save_settings()
        self._settings_changed = False
        
        # Reset button after 1.5 seconds
        def reset_button():
            self.save_settings_btn.setText(original_text)
            self.save_settings_btn.setStyleSheet("")  # Reset to default
            self.save_settings_btn.setEnabled(True)
            self.buttons_row.hide()
        
        QTimer.singleShot(1500, reset_button)
    
    def _cancel_settings_changes(self):
        """Cancel changes and reload original settings."""
        self._load_settings()
        self._settings_changed = False
        self.buttons_row.hide()
        self.status_label.setText("Изменения отменены")
    
    def _on_setting_changed(self):
        """Called when any setting is changed."""
        if not self._settings_changed:
            self._settings_changed = True
            self.buttons_row.show()
    
    def _connect_settings_signals(self):
        """Connect all settings widgets to change tracking."""
        self.api_key_input.textChanged.connect(self._on_setting_changed)
        self.proxy_mode_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.proxy_mode_combo.currentIndexChanged.connect(self._update_proxy_ui)
        self.proxy_input.textChanged.connect(self._on_setting_changed)
        self.model_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.auto_paste_cb.stateChanged.connect(self._on_setting_changed)
        self.auto_copy_cb.stateChanged.connect(self._on_setting_changed)
        self.sound_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.show_widget_on_record_cb.stateChanged.connect(self._on_setting_changed)
        self.sound_enabled_cb.stateChanged.connect(self._on_setting_changed)
    
    def _load_settings(self):
        try:
            path = self._get_settings_path()
            s = {}  # Default empty settings
            
            if os.path.exists(path):
                # Try UTF-8 first, then fallback to system encoding
                try:
                    with open(path, encoding='utf-8') as f:
                        s = json.load(f)
                except UnicodeDecodeError:
                    with open(path, encoding='cp1251') as f:
                        s = json.load(f)
            else:
                log.info("First run - using default settings (no API key)")
            
            # Apply settings (defaults used if not in file)
            self.api_key_input.setText(s.get("api_key", ""))

            legacy_proxy = (s.get("proxy") or "").strip()
            custom_proxy = (s.get("custom_proxy") or "").strip()
            proxy_mode = s.get("proxy_mode")

            if not proxy_mode:
                if legacy_proxy:
                    proxy_mode = "built_in"
                    if not self._load_internal_proxy():
                        self._save_internal_proxy(legacy_proxy)
                else:
                    proxy_mode = "custom"

            if proxy_mode == "custom":
                self.proxy_input.setText(custom_proxy or legacy_proxy)
            else:
                self.proxy_input.setText(custom_proxy)

            proxy_mode_index = self.proxy_mode_combo.findData(proxy_mode)
            if proxy_mode_index < 0:
                proxy_mode_index = 0
            self.proxy_mode_combo.setCurrentIndex(proxy_mode_index)
            self._update_proxy_ui()

            self.hotkey_input.setText(s.get("hotkey", "alt+`"))
            self.cancel_hotkey_input.setText(s.get("cancel_hotkey", "alt+1"))
            self.auto_paste_cb.setChecked(s.get("auto_paste", True))
            self.auto_copy_cb.setChecked(s.get("auto_copy", True))
                
            # Load model - try index first, then data
            model_idx = s.get("model_index", -1)
            if model_idx >= 0 and model_idx < self.model_combo.count():
                self.model_combo.setCurrentIndex(model_idx)
            else:
                idx = self.model_combo.findData(s.get("model"))
                if idx >= 0: 
                    self.model_combo.setCurrentIndex(idx)
            print(f"[SETTINGS] Loaded model: {self.model_combo.currentData()} (index {self.model_combo.currentIndex()})")
            
            # Load language - try index first, then data
            lang_idx = s.get("language_index", -1)
            if lang_idx >= 0 and lang_idx < self.language_combo.count():
                self.language_combo.setCurrentIndex(lang_idx)
            else:
                idx = self.language_combo.findData(s.get("language", "Russian"))
                if idx >= 0:
                    self.language_combo.setCurrentIndex(idx)
            
            if hasattr(self, 'method_combo'):
                idx = self.method_combo.findData(s.get("method", "live"))
                if idx >= 0: self.method_combo.setCurrentIndex(idx)
            self.show_overlay_cb.setChecked(s.get("show_overlay", True))
            self.show_cost_cb.setChecked(s.get("show_cost", True))
            
            # Load sound - try index first, then data
            sound_idx = s.get("sound_index", -1)
            if sound_idx >= 0 and sound_idx < self.sound_combo.count():
                self.sound_combo.setCurrentIndex(sound_idx)
            else:
                idx = self.sound_combo.findData(s.get("sound"))
                if idx >= 0: self.sound_combo.setCurrentIndex(idx)
                
            self.sound_enabled_cb.setChecked(s.get("sound_enabled", True))
            self.show_widget_on_record_cb.setChecked(s.get("show_widget_on_record", False))
            self.show_realtime_text_cb.setChecked(s.get("show_realtime_text", False))
            self.stats = s.get("stats", self.stats)
            self._update_stats_display()
            
            # Load history_enabled setting
            self.history_enabled = s.get("history_enabled", True)
            self.history_enabled_cb.setChecked(self.history_enabled)
                
        except Exception as e:
            log.error(f"Load settings error: {e}")
            import traceback
            traceback.print_exc()
        
        # Load history from SQLite database
        try:
            self._load_history_from_db()
        except Exception as e:
            log.error(f"Load history error: {e}")
        
        # Connect signals after loading to avoid triggering change detection
        # Only connect once (check if already connected)
        if not getattr(self, '_signals_connected', False):
            self._connect_settings_signals()
            self._signals_connected = True
    
    def _load_history_from_db(self):
        """Load history from SQLite database."""
        try:
            records = self.history_manager.get_page(page=1, per_page=100)
            self.history = []
            for record in records:
                item = {
                    'id': record.id,
                    'text': record.text,
                    'duration': record.duration,
                    'time': record.timestamp.strftime("%H:%M | %d.%m.%Y"),
                    'timestamp': record.timestamp.timestamp(),
                    'audio_file': record.audio_path
                }
                self.history.append(item)
            
            # Recalculate stats from database
            total_count = self.history_manager.get_total_count()
            self.stats['transcriptions'] = total_count
            self.stats['total_duration'] = sum(item.get('duration', 0) for item in self.history)
            self.stats['total_chars'] = sum(len(item.get('text', '')) for item in self.history)
            
            log.info(f"Loaded {len(self.history)} history records from database")
            self._update_history_display()
            self._update_stats_display()
        except Exception as e:
            log.error(f"Failed to load history from database: {e}")
            self.history = []
    
    def _update_stats_display(self):
        self.stat_count.setText(str(self.stats.get('transcriptions', 0)))
        mins = int(self.stats.get('total_duration', 0) // 60)
        secs = int(self.stats.get('total_duration', 0) % 60)
        self.stat_duration.setText(f"{mins}м {secs}с")
        self.stat_chars.setText(str(self.stats.get('total_chars', 0)))

    def _play_sound(self):
        if not self.sound_enabled_cb.isChecked():
            return
        sound_id = self.sound_combo.currentData()
        sounds_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "sounds", "clicks")
        filepath = os.path.join(sounds_dir, f"{sound_id}.wav")
        try:
            sd.stop()
            if os.path.exists(filepath):
                with wave.open(filepath, 'rb') as wf:
                    data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                    sample_rate = wf.getframerate()
                threading.Thread(target=lambda: sd.play(data, sample_rate), daemon=True).start()
                return

            # Fallback: synthesize a short camera-like click so sound feedback still works
            sample_rate = 44100
            duration = 0.06
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            env = np.exp(-45 * t)
            click = 0.45 * env * (
                np.sin(2 * np.pi * 1400 * t) +
                0.5 * np.sin(2 * np.pi * 2200 * t) +
                0.25 * np.sin(2 * np.pi * 3200 * t)
            )
            click = np.clip(click.astype(np.float32), -1.0, 1.0)
            threading.Thread(target=lambda: sd.play(click, sample_rate), daemon=True).start()
        except Exception as e:
            print(f"Sound error: {e}")
            try:
                if sys.platform == 'win32':
                    import winsound
                    winsound.MessageBeep()
            except Exception:
                pass
    
    @pyqtSlot()
    def _toggle_recording(self):
        # Debounce: prevent double trigger within 1 second
        current_time = time.time()
        last_toggle = getattr(self, '_last_toggle_time', 0)
        if current_time - last_toggle < 1.0:
            print(f"[DEBOUNCE] Ignoring toggle, too fast ({current_time - last_toggle:.2f}s)")
            return
        self._last_toggle_time = current_time
        
        log.info(f"[TOGGLE] is_recording={self.is_recording}")
        
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()
    
    @pyqtSlot()
    def _cancel_recording(self):
        """Cancel recording without transcription (discard audio)."""
        if not self.is_recording:
            return
        
        print("[CANCEL] Cancelling recording...")
        self.is_recording = False
        
        # Stop pre-upload timer
        if hasattr(self, '_pre_upload_timer'):
            self._pre_upload_timer.stop()
        
        # Stop recorder without saving
        self.recorder.on_chunk_callback = None
        self.recorder.stop_recording()
        
        # Clear streaming frames
        self._streaming_frames = []
        
        # Reset UI
        self.record_btn.setText("Начать запись")
        self.record_btn.setStyleSheet("")
        self.status_label.setText("Запись отменена")
        self.recording_widget.set_idle()
        
        print("[CANCEL] Recording discarded")
    
    def _start_recording(self):
        if not self.api_key_input.text().strip():
            self.signals.error.emit("Please enter API key first")
            return
        log.info("Starting recording")
        self.is_recording = True
        self._play_sound()
        
        # Initialize Chunked transcriber for parallel processing
        self._streaming_frames = []
        
        # Get proxy if configured
        proxy_url = self._get_effective_proxy()
        model = self.model_combo.currentData() or "gemini-2.5-flash"
        language = self.language_combo.currentData() or "Russian"
        
        # Create ChunkedTranscriber for fast parallel transcription
        self._chunked_transcriber = ChunkedTranscriber(
            api_key=self.api_key_input.text().strip(),
            model=model,
            proxy_url=proxy_url,
            language=language,
            on_chunk_result=self._on_chunk_result,
            on_error=self._on_chunked_error
        )
        
        # Start chunked transcriber
        self._chunked_transcriber.start()
        
        # Configure recorder callback to send chunks
        self.recorder.on_chunk_callback = self._on_audio_chunk_live
        self.recorder.start_recording()
        
        self.record_btn.setText("Остановить запись")
        self.record_btn.setStyleSheet(f"background-color: {self.COLORS['error']};")
        self.status_label.setText("Запись...")
        
        # Clear real-time text
        self.recording_widget.clear_realtime_text()
        
        # Show recording widget if setting is enabled (without stealing focus)
        if self.show_widget_on_record_cb.isChecked():
            self.recording_widget.setWindowFlags(
                self.recording_widget.windowFlags() | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.recording_widget.show()
            self.recording_widget.raise_()
        
        # Update recording widget
        log.info(f"[WIDGET] Calling set_recording(), widget visible={self.recording_widget.isVisible()}")
        self.recording_widget.set_recording()
        log.info(f"[WIDGET] set_recording() done, state={self.recording_widget._state}")
    
    def _on_audio_chunk_live(self, chunk: bytes):
        """Callback for chunked transcriber - sends chunks for parallel processing."""
        self._streaming_frames.append(chunk)
        
        # Send to chunked transcriber
        if hasattr(self, '_chunked_transcriber') and self._chunked_transcriber:
            self._chunked_transcriber.add_audio(chunk)
        
        # Calculate audio level for waveform animation
        try:
            audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            rms = np.sqrt(np.mean(audio_data ** 2))
            level = min(1.0, max(0.0, (rms - 200) / 3000))
            self.signals.audio_level.emit(level)
        except Exception as e:
            print(f"Audio chunk error: {e}")
    
    def _on_chunk_result(self, chunk_idx: int, text: str):
        """Callback for chunk transcription result."""
        log.debug(f"[CHUNKED] Chunk {chunk_idx} result: {text[:50]}...")
        
        # Update UI if real-time display is enabled (call directly, already thread-safe via signal)
        if self.show_realtime_text_cb.isChecked() and hasattr(self, '_chunked_transcriber'):
            partial = self._chunked_transcriber.get_partial_result()
            # Use signals.status_update instead of direct method call
            self.signals.status_update.emit(f"Чанк {chunk_idx}: {len(text)} символов")
    
    def _on_chunked_error(self, error: str):
        """Callback for chunked transcriber errors."""
        log.error(f"[CHUNKED] Error: {error}")
        self.signals.error.emit(f"Transcription: {error[:40]}")
    
    def _on_audio_chunk(self, chunk: bytes):
        """Legacy callback - redirects to live version."""
        self._on_audio_chunk_live(chunk)
    
    def _on_audio_level(self, level: float):
        """Handle audio level signal in main thread."""
        self.recording_widget.waveform.set_level(level)
    
    def _start_pre_upload(self):
        """Начинаем upload аудио пока ещё идёт запись."""
        if not self.is_recording or self._pre_upload_started:
            return
        
        self._pre_upload_started = True
        # Запускаем upload в отдельном потоке
        threading.Thread(target=self._do_pre_upload, daemon=True).start()
    
    def _do_pre_upload(self):
        """Pre-upload disabled - using REST API with inline_data instead."""
        # Pre-upload через genai.upload_file() не работает из-за региональных ограничений
        # REST API использует inline_data, поэтому pre-upload не нужен
        self._pre_uploaded_file = None
        pass
    
    def _stop_recording(self):
        log.info("Stopping recording")
        self.is_recording = False
        self._play_sound()
        
        self.record_btn.setText("Начать запись")
        self.record_btn.setStyleSheet("")
        self.status_label.setText("Завершение...")
        
        # Short delay to capture last words without adding too much latency
        QTimer.singleShot(100, self._finish_recording)
    
    def _finish_recording(self):
        """Stop recording and get transcription from chunked transcriber."""
        audio_file, duration = self.recorder.stop_recording()
        self.recorder.on_chunk_callback = None
        
        # Store audio file path for history
        self._last_audio_file = audio_file
        
        self.status_label.setText("Обработка...")
        self.recording_widget.set_processing(duration)
        self._transcription_start_time = time.time()
        
        # Get transcription from chunked transcriber
        if hasattr(self, '_chunked_transcriber') and self._chunked_transcriber:
            # Stop chunked transcriber and get result
            threading.Thread(
                target=self._finish_chunked_transcription,
                args=(audio_file, duration),
                daemon=True
            ).start()
        else:
            # Fallback to REST API if chunked not available
            if audio_file:
                threading.Thread(target=self._process_audio, args=(audio_file, duration)).start()
    
    def _finish_chunked_transcription(self, audio_file, duration):
        """Finish chunked transcription and emit result."""
        try:
            # Stop transcriber and get final combined text
            text = self._chunked_transcriber.stop()
            
            if text:
                log.info(f"[CHUNKED] Final transcription: {len(text)} chars")
                cost = (duration / 60.0) * 0.0015
                self.signals.finished.emit(text, duration, cost)
            else:
                log.warning("[CHUNKED] No transcription received, falling back to REST API")
                # Fallback to REST API
                self._process_audio_standard(audio_file, duration)
                
        except Exception as e:
            log.error(f"[CHUNKED] Finish error: {e}")
            # Fallback to REST API
            self._process_audio_standard(audio_file, duration)
        finally:
            self._chunked_transcriber = None
    
    def _process_audio(self, audio_file, duration):
        """Process audio using REST API (fallback)."""
        model = self.model_combo.currentData() or "gemini-2.5-flash"
        log.info(f"Processing audio (REST fallback): {audio_file}, duration: {duration:.1f}s, model: {model}")
        self._process_audio_standard(audio_file, duration)
    
    def _process_audio_standard(self, audio_file, duration):
        """Process audio using direct REST API (bypasses SDK regional restrictions)."""
        try:
            import base64
            import requests
            t0 = time.time()
            
            api_key = self.api_key_input.text().strip()
            model = self.model_combo.currentData() or "gemini-2.5-flash"
            cost = (duration / 60.0) * 0.0015
            
            # Замер: размер файла
            file_size = os.path.getsize(audio_file) / 1024
            log.debug(f"Audio file size: {file_size:.1f} KB")
            
            # Читаем и кодируем аудио
            t1 = time.time()
            with open(audio_file, 'rb') as f:
                audio_bytes = f.read()
            
            mime_type = "audio/flac" if audio_file.endswith('.flac') else "audio/wav"
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            t2 = time.time()
            log.debug(f"Audio prepare time: {t2-t1:.3f}s")
            
            # Прямой REST API запрос (обходит ограничения SDK)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Transcribe this audio exactly as spoken. Use Cyrillic for Russian words and Latin script for English technical terms, brand names, acronyms, and anglicisms. Do not transliterate English terms into Cyrillic. Normalize keyboard shortcuts in the form 'Ctrl + Shift + V', 'Alt + 1', 'Ctrl + C'. Add natural punctuation and capitalization. Return ONLY the final transcribed text."},
                        {"inline_data": {"mime_type": mime_type, "data": audio_base64}}
                    ]
                }]
            }
            
            # Proxy support
            proxies = None
            proxy_url = self._get_effective_proxy()
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}
                log.info("Using configured proxy mode for request")
            
            response = requests.post(url, json=payload, timeout=60, proxies=proxies)
            t3 = time.time()
            
            if response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', response.text)
                raise Exception(f"API error {response.status_code}: {error_msg}")
            
            result = response.json()
            text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            text = text.strip()
            
            log.info(f"Transcription completed in {t3-t2:.2f}s (total: {t3-t0:.2f}s)")
            log.info(f"Transcribed {len(text)} characters")
            self.signals.finished.emit(text, duration, cost)
            
        except Exception as e:
            log.error(f"Transcription error: {e}")
            self.signals.error.emit(str(e))
    
    def _on_transcription_finished(self, text, duration, cost):
        # Prevent double paste
        if getattr(self, '_paste_in_progress', False):
            print("[WARN] Paste already in progress, skipping")
            return
        self._paste_in_progress = True
        
        # Сохраняем данные для отложенной вставки
        self._pending_text = text
        self._pending_duration = duration
        self._pending_cost = cost
        
        # Для вставки нужно сначала скопировать в буфер
        need_paste = self.auto_paste_cb.isChecked()
        need_copy = self.auto_copy_cb.isChecked()
        
        # Сохраняем старое содержимое буфера если нужна только вставка без копирования
        self._restore_clipboard = False
        if need_paste and not need_copy:
            try:
                self._old_clipboard = pyperclip.paste()
                self._restore_clipboard = True
            except:
                self._old_clipboard = ""
        
        # Копируем в буфер (всегда если нужна вставка, или если включено копирование)
        if need_paste or need_copy:
            pyperclip.copy(text)
        
        # Вставляем в текстовое поле (если включено)
        if need_paste:
            # Keep paste nearly immediate to reduce perceived latency
            QTimer.singleShot(75, self._do_paste)
            # Update UI shortly after paste without waiting a full second
            QTimer.singleShot(200, self._do_update_ui)
        else:
            # Update UI almost immediately when no paste is needed
            QTimer.singleShot(50, self._do_update_ui)
    
    def _do_paste(self):
        """Paste text to active text field using Windows API."""
        # Prevent double paste - check if already pasted recently
        current_time = time.time()
        last_paste = getattr(self, '_last_paste_time', 0)
        if current_time - last_paste < 1.0:
            log.warning(f"[PASTE] Skipping duplicate paste ({current_time - last_paste:.2f}s since last)")
            return
        self._last_paste_time = current_time
        
        log.info("[PASTE] Starting paste...")
        
        try:
            import ctypes
            
            # Windows API constants
            VK_CONTROL = 0x11
            VK_SHIFT = 0x10
            VK_V = 0x56
            KEYEVENTF_KEYUP = 0x0002
            
            user32 = ctypes.windll.user32
            
            # Отпускаем все модификаторы через Windows API
            user32.keybd_event(0x12, 0, KEYEVENTF_KEYUP, 0)  # Alt up
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)  # Ctrl up
            user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)  # Shift up
            
            time.sleep(0.12)
            
            # Отправляем Ctrl+Shift+V через Windows API
            user32.keybd_event(VK_CONTROL, 0, 0, 0)  # Ctrl down
            time.sleep(0.02)
            user32.keybd_event(VK_SHIFT, 0, 0, 0)  # Shift down
            time.sleep(0.02)
            user32.keybd_event(VK_V, 0, 0, 0)  # V down
            time.sleep(0.03)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)  # V up
            time.sleep(0.02)
            user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)  # Shift up
            time.sleep(0.02)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)  # Ctrl up
            
            log.info("[PASTE] Sent ctrl+shift+v via Windows API")
            
        except Exception as e:
            log.warning(f"[PASTE] Windows API failed: {e}, trying pyautogui")
            try:
                pyautogui.FAILSAFE = False
                pyautogui.hotkey('ctrl', 'shift', 'v', interval=0.05)
                log.info("[PASTE] Sent ctrl+shift+v via pyautogui (fallback)")
            except Exception as e2:
                log.error(f"[PASTE] All methods failed: {e2}")
        
        # Восстанавливаем старое содержимое буфера если нужно
        if getattr(self, '_restore_clipboard', False):
            QTimer.singleShot(200, self._restore_old_clipboard)
    
    def _restore_old_clipboard(self):
        """Restore old clipboard content after paste."""
        try:
            old = getattr(self, '_old_clipboard', '')
            if old:
                pyperclip.copy(old)
        except:
            pass
        self._restore_clipboard = False
    
    def _do_update_ui(self):
        """Update UI after transcription."""
        # Reset paste flag
        self._paste_in_progress = False
        
        # Обновляем UI
        text = self._pending_text
        duration = self._pending_duration
        cost = self._pending_cost
        
        self.stats['transcriptions'] += 1
        self.stats['total_duration'] += duration
        self.stats['total_chars'] += len(text)
        self._update_stats_display()
        
        self._add_to_history(text, duration, getattr(self, '_last_audio_file', None))
        self._save_settings()
        
        self.status_label.setText("Готово!")
        
        # Update recording widget with transcription time
        transcription_time = time.time() - getattr(self, '_transcription_start_time', time.time())
        self.recording_widget.set_success(transcription_time)
        
        # Hide recording widget after 3 seconds if setting is enabled
        if self.show_widget_on_record_cb.isChecked():
            QTimer.singleShot(3000, self._hide_recording_widget_if_idle)
    
    def _hide_recording_widget_if_idle(self):
        """Hide recording widget if not currently recording."""
        if not self.is_recording and self.show_widget_on_record_cb.isChecked():
            self.recording_widget.hide()
    
    def _on_error(self, msg):
        self.status_label.setText(f"Ошибка: {msg[:50]}")
        self.recording_widget.set_error(msg[:25])
        
        # Also hide widget on error after 3 seconds
        if self.show_widget_on_record_cb.isChecked():
            QTimer.singleShot(3000, self._hide_recording_widget_if_idle)
    
    def _update_status(self, msg):
        self.status_label.setText(msg)
    
    def _show_settings(self):
        """Show settings window on top of all windows."""
        self.show()
        self.raise_()
        self.activateWindow()
    
    def _quit(self):
        log.info("Application closing")
        self._save_settings()
        

        
        # Unregister all hotkeys
        try:
            keyboard.unhook_all_hotkeys()
        except:
            pass
        
        # Close database connection
        if hasattr(self, 'history_manager'):
            self.history_manager.close()
        self.recording_widget.hide()
        QApplication.quit()
    
    def closeEvent(self, event):
        # Сворачиваем в tray вместо закрытия
        event.ignore()
        self.hide()
