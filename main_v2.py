"""Gemini Voice Writer v2 - Modern UI."""
import sys
from PyQt6.QtWidgets import QApplication
from core.recorder import AudioRecorder
from core.transcriber import GeminiTranscriber
from ui.main_window_v2 import MainWindowV2


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    recorder = AudioRecorder()
    window = MainWindowV2(recorder, GeminiTranscriber, None)
    # Don't show settings window on startup - only recording widget is shown
    # window.show()  # Settings window opens only via Settings button
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
