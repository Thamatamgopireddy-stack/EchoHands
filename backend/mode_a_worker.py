"""Offline webcam hand-gesture worker."""

import os
import queue
import threading
import time
import json
import math

GESTURE_WORDS = {
    "OPEN_HAND": "hello",
    "FIST": "no",
    "POINTING": "please",
    "VICTORY_V": "thank you",
    "THUMBS_UP": "yes",
    "THUMBS_DOWN": "no",
}


class LandmarkClassifier:
    """Match normalized MediaPipe landmarks against static hand templates."""

    def __init__(self, templates_path=None, threshold=0.65):
        if templates_path is None:
            root = os.path.dirname(os.path.dirname(__file__))
            templates_path = os.path.join(root, "assets", "sign_landmarks.json")
        with open(templates_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        self.threshold = threshold
        self.templates = {
            name: self._normalize(points)
            for name, value in data.items()
            if (points := value.get("landmarks")) and len(points) == 21
        }

    @staticmethod
    def _normalize(points):
        translated = [
            [point[axis] - points[0][axis] for axis in range(3)]
            for point in points
        ]
        scale = math.sqrt(sum(value * value for value in translated[9]))
        if scale == 0:
            return None
        return [value / scale for point in translated for value in point]

    @staticmethod
    def _landmark_coordinates(landmarks):
        return [[landmark.x, landmark.y, landmark.z] for landmark in landmarks]

    def classify(self, landmarks):
        if len(landmarks) != 21:
            return None
        live_vector = self._normalize(self._landmark_coordinates(landmarks))
        if live_vector is None:
            return None
        best_match, min_distance = None, float("inf")
        for name, reference in self.templates.items():
            distance = math.sqrt(sum(
                (live - target) ** 2 for live, target in zip(live_vector, reference)
            ))
            if distance < min_distance:
                best_match, min_distance = name, distance
        return best_match if min_distance < self.threshold else None


_CLASSIFIER = None


def classify_landmarks(landmarks):
    """Classify a MediaPipe hand landmark list using the template library."""
    global _CLASSIFIER
    if _CLASSIFIER is None:
        _CLASSIFIER = LandmarkClassifier()
    return _CLASSIFIER.classify(landmarks)


class ModeAWorker:
    def __init__(self, event_queue, tts_queue, frame_queue=None, model_path=None):
        self.events, self.tts_queue, self.frames = event_queue, tts_queue, frame_queue
        self.model_path = model_path
        self.running = threading.Event()
        self.thread = None

    def start(self):
        if self.running.is_set():
            return
        self.running.set()
        self.thread = threading.Thread(target=self._run, name="echohands-camera", daemon=True)
        self.thread.start()

    def stop(self):
        self.running.clear()

    def _run(self):
        import cv2
        import mediapipe as mp
        cap = None
        for index in range(5):
            candidate = cv2.VideoCapture(index)
            if candidate.isOpened():
                cap = candidate
                break
            candidate.release()
        if cap is None:
            self.events.put(("error", "No camera found (checked indexes 0-4)."))
            return
        root = os.path.dirname(os.path.dirname(__file__))
        model = self.model_path or os.path.join(root, "models", "hand_landmarker.task")
        if not os.path.isfile(model):
            model = os.path.join(root, "hand_landmarker.task")
        try:
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=model), running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=1, min_hand_detection_confidence=0.65, min_hand_presence_confidence=0.65, min_tracking_confidence=0.65)
            with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
                self._capture(cap, landmarker, cv2, mp)
        except Exception as error:
            self.events.put(("error", f"Camera worker stopped: {error}"))
        finally:
            cap.release()
            cv2.destroyAllWindows()

    def _capture(self, cap, landmarker, cv2, mp):
        previous, stable_count, last_spoken = None, 0, {}
        while self.running.is_set():
            ok, frame = cap.read()
            if not ok:
                self.events.put(("error", "Camera frame was not received."))
                break
            frame = cv2.flip(frame, 1)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            result = landmarker.detect_for_video(image, int(time.monotonic() * 1000))
            gesture = classify_landmarks(result.hand_landmarks[0]) if result.hand_landmarks else None
            if gesture and gesture == previous:
                stable_count += 1
            else:
                previous, stable_count = gesture, 1
            if gesture and stable_count >= 8 and time.monotonic() - last_spoken.get(gesture, 0) >= 2.0:
                word = GESTURE_WORDS.get(gesture, gesture.replace("_", " ").lower())
                self.events.put(("sign", f"{gesture}: {word}"))
                self.tts_queue.put(word)
                last_spoken[gesture] = time.monotonic()
            if self.frames is not None:
                try:
                    self.frames.put_nowait((frame, gesture))
                except queue.Full:
                    try:
                        self.frames.get_nowait()
                        self.frames.put_nowait((frame, gesture))
                    except queue.Empty:
                        pass