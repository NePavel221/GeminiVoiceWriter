import pyaudio
import wave
import threading
import os
import time
import tempfile

class AudioRecorder:
    def __init__(self, output_filename=None):
        if output_filename is None:
            self.output_filename = os.path.join(tempfile.gettempdir(), "GeminiVoiceWriter_audio.wav")
        else:
            self.output_filename = output_filename
        self.is_recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
        # Audio configuration
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.CHUNK = 1024

    def start_recording(self):
        if self.is_recording:
            print("Recorder: Already recording.")
            return
        
        print("Recorder: Starting...")
        self.is_recording = True
        self.frames = []
        
        try:
            self.stream = self.audio.open(format=self.FORMAT,
                                          channels=self.CHANNELS,
                                          rate=self.RATE,
                                          input=True,
                                          frames_per_buffer=self.CHUNK)
            print("Recorder: Stream opened.")
        except Exception as e:
            print(f"Recorder: Failed to open stream: {e}")
            self.is_recording = False
            return
        
        self.thread = threading.Thread(target=self._record)
        self.thread.start()
        print("Recorder: Thread started.")

    def _record(self):
        print("Recorder: Loop started.")
        while self.is_recording:
            try:
                data = self.stream.read(self.CHUNK)
                self.frames.append(data)
            except Exception as e:
                print(f"Recorder: Error reading stream: {e}")
                break
        print("Recorder: Loop finished.")

    def stop_recording(self):
        if not self.is_recording:
            return None, 0
            
        print("Recorder: Stopping...")
        self.is_recording = False
        
        # We don't join immediately if read is blocking, but read should return fast.
        # If it hangs, we might need to close stream from another thread?
        # PyAudio documentation suggests stopping stream first?
        # But if we stop stream, read might throw exception.
        
        try:
            if self.thread.is_alive():
                self.thread.join(timeout=1.0) # Wait max 1 second
                if self.thread.is_alive():
                    print("Recorder: Thread did not exit in time.")
        except Exception as e:
            print(f"Recorder: Error joining thread: {e}")

        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                print("Recorder: Stream closed.")
        except Exception as e:
            print(f"Recorder: Error closing stream: {e}")
        
        return self._save_to_file()

    def _save_to_file(self):
        try:
            wf = wave.open(self.output_filename, 'wb')
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            print(f"Recorder: Saved to {self.output_filename}")
            
            # Calculate duration
            duration = len(self.frames) * self.CHUNK / self.RATE
            return os.path.abspath(self.output_filename), duration
        except Exception as e:
            print(f"Recorder: Error saving file: {e}")
            return None, 0

    def __del__(self):
        try:
            self.audio.terminate()
        except:
            pass
