"""Threaded MediaPipe camera and gesture pipeline."""

import queue
import threading
import time
from typing import Optional

import cv2

from hand_keypoints import HandKeypointDetector


class ModeAEngine:
    def __init__(self, events_queue=None, frames_queue=None, tts_queue=None, model_path: Optional[str] = None):
        self.events = events_queue
        self.frames = frames_queue
        self.tts_queue = tts_queue
        self.model_path = model_path
        self.running = threading.Event()
        self.thread = None
        self.cap = None
        self.hand_detector = None
        self.last_gesture = None
        self.stable_count = 0
        self.last_spoken = {}

    def start(self, cam_index=0):
        if self.running.is_set():
            return True
        capture = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(cam_index)
        if not capture.isOpened():
            capture.release()
            self._event("error", "Camera failed to open.")
            return False
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)
        self.cap = capture
        self.running.set()
        self.thread = threading.Thread(target=self._loop, name="ModeA-Worker", daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running.clear()
        capture = self.cap
        self.cap = None
        if capture is not None:
            capture.release()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.0)
        self.thread = None

    def _event(self, kind, message):
        if self.events:
            self.events.put((kind, message))

    def _publish_gesture(self, gesture):
        now = time.monotonic()
        if gesture != self.last_gesture:
            self.last_gesture = gesture
            self.stable_count = 1
            return
        self.stable_count += 1
        if self.stable_count < 6 or now - self.last_spoken.get(gesture, 0.0) < 1.8:
            return
        self.last_spoken[gesture] = now
        self._event("sign", f"{gesture}: {gesture}")
        if self.tts_queue:
            self.tts_queue.put(gesture.replace("_", " "))

    def _loop(self):
        capture = self.cap
        try:
            self.hand_detector = HandKeypointDetector(self.model_path)
            self._event("info", "Camera feed active")
            while self.running.is_set() and capture is not None:
                ok, frame = capture.read()
                if not ok:
                    self._event("error", "Camera frame lost.")
                    break
                frame = cv2.flip(frame, 1)
                _, gesture = self.hand_detector.detect(frame)
                self._publish_gesture(gesture)
                display_gesture = gesture or "WAITING FOR HAND"
                if self.frames:
                    try:
                        if self.frames.full():
                            self.frames.get_nowait()
                        self.frames.put_nowait((frame, display_gesture))
                    except (queue.Empty, queue.Full):
                        pass
                time.sleep(0.005)
        except Exception as error:
            self._event("error", f"Camera worker stopped: {error}")
        finally:
            if self.hand_detector:
                self.hand_detector.close()
                self.hand_detector = None
            self.running.clear()
            if capture is not None:
                capture.release()
