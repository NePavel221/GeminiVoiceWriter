import keyboard
import threading
import time

class HotkeyManager:
    def __init__(self, hotkey, on_trigger_callback):
        self.hotkey = hotkey
        self.on_trigger = on_trigger_callback
        self.running = False
        self.last_trigger_time = 0
        self.cooldown = 0.5  # Prevent double triggering

    def start(self):
        self.running = True
        print(f"Attempting to register hotkey: {self.hotkey}")
        try:
            keyboard.add_hotkey(self.hotkey, self._on_press)
            print(f"Hotkey '{self.hotkey}' registered successfully.")
        except Exception as e:
            print(f"Failed to register hotkey: {e}")
            self.running = False
            raise e

    def stop(self):
        self.running = False
        try:
            keyboard.remove_hotkey(self.hotkey)
            print(f"Hotkey '{self.hotkey}' removed.")
        except:
            pass

    def update_hotkey(self, new_hotkey):
        if self.hotkey == new_hotkey:
            return
            
        print(f"Updating hotkey from '{self.hotkey}' to '{new_hotkey}'")
        self.stop()
        self.hotkey = new_hotkey
        self.start()

    def _on_press(self):
        print(f"Hotkey '{self.hotkey}' triggered!")
        current_time = time.time()
        if current_time - self.last_trigger_time > self.cooldown:
            self.last_trigger_time = current_time
            if self.running:
                self.on_trigger()
