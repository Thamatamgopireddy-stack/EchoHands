# -*- coding: utf-8 -*-
"""Mode A camera engine that streams processed frames to the WebView."""

import cv2
import threading
import time

from hand_keypoints import HandKeypointDetector


class ModeAEngine:
    def __init__(self, events_queue=None, frames_queue=None, tts_queue=None):
        self.events = events_queue
        self.frames = frames_queue
        self.tts_queue = tts_queue
        self.running = False
        self.thread = None
        self.cap = None
        self.hand_detector = HandKeypointDetector()
        self.last_pose = None
        self.last_pose_time = 0.0

    def start(self, cam_index=0):
        if self.running:
            return True
        self.cap = cv2.VideoCapture(cam_index)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            self._event("error", "Camera failed to open.")
            return False
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="ModeA-Worker", daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    def _event(self, kind, message):
        if self.events:
            self.events.put((kind, message))

    def _loop(self):
        self._event("info", "Camera feed active")
        pose_to_word = {
            "OPEN HAND": "HELLO",
            "TWO FINGERS": "YES",
            "FIST": "NO",
            "ONE FINGER": "PLEASE",
            "PARTIAL HAND": "THANK_YOU",
        }
        while self.running and self.cap:
            ret, frame = self.cap.read()
            if not ret:
                self._event("error", "Camera frame lost.")
                break
            frame = cv2.flip(frame, 1)
            frame, hand_count, keypoints = self.hand_detector.detect_and_draw_hand(frame, min_area=500)
            detected_pose = "WAITING FOR HAND"
            if hand_count > 0 and keypoints is not None:
                detected_pose = HandKeypointDetector.get_hand_pose_info(keypoints)
                now = time.monotonic()
                if detected_pose != self.last_pose and now - self.last_pose_time > 1.2:
                    self.last_pose = detected_pose
                    self.last_pose_time = now
                    normalized_pose = detected_pose.upper()
                    word = next(
                        (value for key, value in pose_to_word.items() if key in normalized_pose),
                        detected_pose,
                    )
                    self._event("sign", f"{detected_pose}: {word}")
                    if self.tts_queue:
                        self.tts_queue.put(word)
            if self.frames:
                try:
                    if self.frames.full():
                        self.frames.get_nowait()
                    self.frames.put_nowait((frame, detected_pose))
                except Exception:
                    pass
            time.sleep(0.03)