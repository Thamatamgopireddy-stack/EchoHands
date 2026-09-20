# -*- coding: utf-8 -*-
import threading
import time
import speech_recognition as sr


class ModeBEngine:
    """Mode B speech engine that publishes words to the avatar queue."""

    def __init__(self, events_queue=None, publish=None):
        self.events = events_queue
        self.publish = publish
        self.running = False
        self.thread = None
        self.recognizer = sr.Recognizer()
        self.mic = None

    def start(self):
        if self.running:
            return True
        try:
            self.mic = sr.Microphone()
        except Exception as error:
            self._event("error", f"Microphone init failed: {error}")
            return False
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False

    def _event(self, kind, message):
        if self.events:
            self.events.put((kind, message))

    def _loop(self):
        self._event("info", "Listening for speech...")
        try:
            with self.mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except Exception as error:
            self._event("error", f"Ambient noise check failed: {error}")
            self.running = False
            return

        while self.running:
            try:
                with self.mic as source:
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=4)

                text = self.recognizer.recognize_google(audio)
                if text:
                    self._event("speech", text)
                    if self.publish:
                        self.publish([word.upper() for word in text.split() if word.strip()])

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as error:
                self._event("error", f"Mic error: {error}")

            time.sleep(0.1)