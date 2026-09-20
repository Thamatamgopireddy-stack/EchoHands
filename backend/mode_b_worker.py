"""Offline PyAudio/Vosk speech worker and gloss tokenizer."""

import json
import os
import re
import threading

AVAILABLE_SIGNS = {"NAMASTE", "HELLO", "THANK_YOU", "YES", "NO"}


def tokenize_speech(text):
    words = re.sub(r"[^A-Z0-9\s]", " ", text.upper()).split()
    aliases = {"NAMASTHE": "NAMASTE", "THANKYOU": "THANK_YOU"}
    tokens = []
    for word in words:
        word = aliases.get(word, word)
        tokens.append(word) if word in AVAILABLE_SIGNS else tokens.extend(word)
    return tokens


class ModeBWorker:
    def __init__(self, event_queue, publish, model_path=None):
        self.events, self.publish, self.model_path = event_queue, publish, model_path
        self.running = threading.Event()
        self.thread = None

    def start(self):
        if self.running.is_set():
            return
        self.running.set()
        self.thread = threading.Thread(target=self._run, name="echohands-microphone", daemon=True)
        self.thread.start()

    def stop(self):
        self.running.clear()

    def _run(self):
        try:
            import pyaudio
            from vosk import KaldiRecognizer, Model
            root = os.path.dirname(os.path.dirname(__file__))
            model_path = self.model_path or os.path.join(root, "models", "vosk-model-small-en-us")
            if not os.path.isdir(model_path):
                raise FileNotFoundError(f"Vosk model not found: {model_path}")
            audio = pyaudio.PyAudio()
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
            recognizer = KaldiRecognizer(Model(model_path), 16000)
            self.events.put(("info", "Offline microphone listening."))
            while self.running.is_set():
                data = stream.read(4000, exception_on_overflow=False)
                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "").strip()
                    if text:
                        tokens = tokenize_speech(text)
                        self.events.put(("speech", f"{text} -> {' '.join(tokens)}"))
                        self.publish(tokens)
            stream.stop_stream()
            stream.close()
            audio.terminate()
        except Exception as error:
            self.events.put(("error", f"Microphone worker stopped: {error}"))