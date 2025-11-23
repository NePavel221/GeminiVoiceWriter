import keyboard
import time

print("Press 'alt+t' to test hotkey. Press 'esc' to exit.")

def on_trigger():
    print("HOTKEY TRIGGERED!")

keyboard.add_hotkey('alt+t', on_trigger)

keyboard.wait('esc')
print("Exiting...")
