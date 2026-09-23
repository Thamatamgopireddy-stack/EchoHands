"""Non-blocking offline microphone listener for speech-to-sign playback."""

import json
import os
import threading


class ModeBEngine:
    def __init__(self, events_queue=None, publish=None, model_path=None):
        self.events = events_queue
        self.publish = publish
        self.model_path = model_path
        self.running = threading.Event()
        self.thread = None

    def start(self):
        if self.running.is_set():
            return True
        self.running.set()
        self.thread = threading.Thread(target=self._listen_loop, name="ModeB-Worker", daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running.clear()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.0)
        self.thread = None

    def _event(self, kind, message):
        if self.events:
            self.events.put((kind, message))

    def _listen_loop(self):
        audio = None
        stream = None
        try:
            import pyaudio
            from vosk import KaldiRecognizer, Model

            root = os.path.dirname(os.path.abspath(__file__))
            model_path = self.model_path or os.path.join(root, "models", "vosk-model-small-en-us-0.15")
            if not os.path.isdir(model_path):
                raise FileNotFoundError(f"Offline speech model not found: {model_path}")

            self._event("info", "Calibrating microphone...")
            audio = pyaudio.PyAudio()
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
            recognizer = KaldiRecognizer(Model(model_path), 16000)
            self._event("info", "Listening for speech...")
            while self.running.is_set():
                data = stream.read(4000, exception_on_overflow=False)
                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "").strip()
                    if text:
                        tokens = [word.upper() for word in text.split() if word.strip()]
                        self._event("speech", text)
                        if self.publish and tokens:
                            self.publish(tokens)
        except Exception as error:
            self._event("error", f"Microphone listener stopped: {error}")
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            if audio is not None:
                audio.terminate()
            self.running.clear()
