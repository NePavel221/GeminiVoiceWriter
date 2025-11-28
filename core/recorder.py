import pyaudio
import wave
import threading
import os
import time
import tempfile
import numpy as np
import soundfile as sf

class AudioRecorder:
    def __init__(self, output_filename=None, on_chunk_callback=None, use_flac=True):
        # Используем FLAC для сжатия (в ~2x меньше WAV)
        self.use_flac = use_flac
        ext = ".flac" if use_flac else ".wav"
        
        if output_filename is None:
            self.output_filename = os.path.join(tempfile.gettempdir(), f"GeminiVoiceWriter_audio{ext}")
        else:
            self.output_filename = output_filename
        self.is_recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.on_chunk_callback = on_chunk_callback  # Callback для streaming
        
        # Audio configuration
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000  # 16kHz — оптимально для распознавания речи
        self.CHUNK = 512   # Меньший буфер для 16kHz

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
                # Вызываем callback для streaming если он есть
                if self.on_chunk_callback:
                    try:
                        self.on_chunk_callback(data)
                    except Exception as cb_err:
                        print(f"Recorder: Callback error: {cb_err}")
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
            # Calculate duration
            duration = len(self.frames) * self.CHUNK / self.RATE
            
            # Конвертируем bytes в numpy array
            audio_data = np.frombuffer(b''.join(self.frames), dtype=np.int16)
            
            if self.use_flac:
                # Сохраняем в FLAC (сжатие ~2x)
                sf.write(self.output_filename, audio_data, self.RATE, format='FLAC')
                file_size = os.path.getsize(self.output_filename)
                print(f"Recorder: Saved FLAC to {self.output_filename} ({file_size/1024:.1f} KB)")
            else:
                # Сохраняем в WAV
                wf = wave.open(self.output_filename, 'wb')
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self.frames))
                wf.close()
                print(f"Recorder: Saved WAV to {self.output_filename}")
            
            return os.path.abspath(self.output_filename), duration
        except Exception as e:
            print(f"Recorder: Error saving file: {e}")
            return None, 0

    def get_frames(self) -> list:
        """Get recorded frames without saving to file."""
        return list(self.frames)
    
    def get_audio_params(self) -> dict:
        """Get audio parameters for external processing."""
        return {
            'channels': self.CHANNELS,
            'sample_width': self.audio.get_sample_size(self.FORMAT),
            'sample_rate': self.RATE,
            'chunk_size': self.CHUNK
        }

    def __del__(self):
        try:
            self.audio.terminate()
        except:
            pass
