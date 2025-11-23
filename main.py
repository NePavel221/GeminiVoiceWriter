import sys
from PyQt6.QtWidgets import QApplication
from core.recorder import AudioRecorder
from core.transcriber import GeminiTranscriber
from core.hotkey_manager import HotkeyManager
from ui.window import MainWindow

def main():
    try:
        with open("debug.log", "w") as f:
            f.write("Starting app...\n")
            
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        
        with open("debug.log", "a") as f:
            f.write("QApplication created.\n")

        recorder = AudioRecorder()
        
        with open("debug.log", "a") as f:
            f.write("Recorder initialized.\n")

        window = MainWindow(recorder, GeminiTranscriber, HotkeyManager)
        window.show()
        
        with open("debug.log", "a") as f:
            f.write("Window shown. Entering event loop.\n")
        
        sys.exit(app.exec())
    except Exception as e:
        with open("debug.log", "a") as f:
            f.write(f"CRASH: {e}\n")
            import traceback
            traceback.print_exc(file=f)
        raise e

if __name__ == "__main__":
    main()
