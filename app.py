"""Launch the EchoHands Three.js avatar and offline Vosk listener."""

import json
import os
import queue
import base64
import threading
import time

import webview

from modeA_engine import ModeAEngine
from modeB_engine import ModeBEngine


class EchoHandsApi:
    def __init__(self, app):
        self._app = app

    def start_camera(self):
        return bool(self._app.camera.start())

    def stop_camera(self):
        self._app.camera.stop()
        return True

    def start_microphone(self):
        started = bool(self._app.microphone.start())
        return started

    def stop_microphone(self):
        self._app.microphone.stop()
        return True


class SignLanguageApp:
    def __init__(self):
        self.window = None
        self.events = queue.Queue()
        self.frames = queue.Queue(maxsize=2)
        self.tts_queue = queue.Queue()
        self.camera = ModeAEngine(self.events, self.frames, self.tts_queue)
        self.microphone = ModeBEngine(self.events)
        self.api = EchoHandsApi(self)
        self._running = threading.Event()

    def on_loaded(self):
        """Start the bridge loops after the WebView has a JavaScript context."""
        self._running.set()
        threading.Thread(target=self._event_loop, name="echohands-events", daemon=True).start()
        threading.Thread(target=self._frame_loop, name="echohands-camera-frames", daemon=True).start()
        threading.Thread(target=self._tts_loop, name="echohands-tts", daemon=True).start()

    def publish_tokens(self, tokens):
        """Play a recognized token sequence in the browser window."""
        if not self.window:
            return
        for token in tokens:
            self.play_sign_on_avatar(token)

    def play_sign_on_avatar(self, sign_name):
        if not self.window:
            return False
        js_name = json.dumps(str(sign_name).strip().upper())
        result = self.window.evaluate_js(f"window.playSign({js_name});")
        return bool(result)

    def _evaluate(self, function_name, *args):
        if not self.window:
            return
        payload = ", ".join(json.dumps(argument) for argument in args)
        self.window.evaluate_js(f"window.{function_name}({payload});")

    def _event_loop(self):
        while self._running.is_set():
            try:
                kind, message = self.events.get_nowait()
            except queue.Empty:
                time.sleep(0.01)
                continue
            if kind == "speech":
                self._evaluate("onBackendSpeech", message)
            elif kind == "sign":
                gesture, _, word = message.partition(": ")
                self._evaluate("onBackendSign", gesture, word or gesture)
                self.play_sign_on_avatar(word or gesture)
            elif kind == "info":
                self._evaluate("onBackendStatus", message)
            elif kind == "error":
                self._evaluate("onBackendError", message)

    def _frame_loop(self):
        last_sent = 0.0
        while self._running.is_set():
            try:
                frame, gesture = self.frames.get_nowait()
            except queue.Empty:
                time.sleep(0.005)
                continue
            now = time.monotonic()
            if now - last_sent < (1 / 30):
                continue
            last_sent = now
            try:
                import cv2
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                if ok:
                    image = base64.b64encode(encoded).decode("ascii")
                    self._evaluate("onBackendCameraFrame", image, gesture or "")
            except Exception as error:
                self._evaluate("onBackendError", f"Camera preview stopped: {error}")

    def _tts_loop(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            while self._running.is_set():
                try:
                    text = self.tts_queue.get_nowait()
                except queue.Empty:
                    time.sleep(0.01)
                    continue
                engine.say(text)
                engine.runAndWait()
        except Exception as error:
            self._evaluate("onBackendError", f"TTS unavailable: {error}")

    def stop(self):
        self._running.clear()
        self.camera.stop()
        self.microphone.stop()


def main():
    app = SignLanguageApp()
    html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    app.window = webview.create_window(
        title="EchoHands - 3D Sign Language Avatar",
        js_api=app.api,
        url=html_file,
        width=980,
        height=720,
        resizable=True,
    )
    app.window.events.loaded += app.on_loaded
    try:
        webview.start(debug=True)
    finally:
        app.stop()


if __name__ == "__main__":
    main()
