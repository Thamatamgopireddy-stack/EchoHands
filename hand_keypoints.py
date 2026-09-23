"""MediaPipe hand landmark detection and geometric gesture recognition."""

import math
import os
import time
from collections import deque
from typing import Optional, Sequence

import cv2
import numpy as np


GESTURES = ("HELLO", "YES", "NO", "THANK_YOU", "PLEASE", "HELP", "NAMASTE")


class GestureClassifier:
    """Classify normalized MediaPipe landmarks using joint geometry and motion."""

    def __init__(self):
        self._wrist_history = deque(maxlen=8)

    @staticmethod
    def _distance(points, first, second):
        return float(np.linalg.norm(points[first] - points[second]))

    @staticmethod
    def _angle(points, first, vertex, second):
        left = points[first] - points[vertex]
        right = points[second] - points[vertex]
        denominator = np.linalg.norm(left) * np.linalg.norm(right)
        if denominator == 0:
            return 0.0
        return math.degrees(math.acos(float(np.clip(np.dot(left, right) / denominator, -1.0, 1.0))))

    def _finger_extended(self, points, mcp, pip, dip, tip):
        pip_angle = self._angle(points, mcp, pip, dip)
        dip_angle = self._angle(points, pip, dip, tip)
        return pip_angle > 145 and dip_angle > 145 and self._distance(points, 0, tip) > self._distance(points, 0, pip) * 1.12

    def _features(self, points):
        fingers = {
            "index": self._finger_extended(points, 5, 6, 7, 8),
            "middle": self._finger_extended(points, 9, 10, 11, 12),
            "ring": self._finger_extended(points, 13, 14, 15, 16),
            "pinky": self._finger_extended(points, 17, 18, 19, 20),
        }
        fingers["thumb"] = self._angle(points, 1, 2, 4) > 125 and self._distance(points, 4, 5) > self._distance(points, 3, 5) * 1.05
        return fingers

    def classify(self, landmarks: Sequence, hand_count: int = 1) -> Optional[str]:
        if len(landmarks) != 21:
            return None
        points = np.asarray([[item.x, item.y, item.z] for item in landmarks], dtype=np.float32)
        palm_scale = max(self._distance(points, 0, 9), 1e-5)
        points = (points - points[0]) / palm_scale
        fingers = self._features(points)
        extended_count = sum(fingers.values())
        pinch_index = self._distance(points, 4, 8) < 0.42
        pinch_middle = self._distance(points, 4, 12) < 0.48
        thumb_up = points[4][1] < points[3][1] - 0.18 and not fingers["index"] and not fingers["middle"]
        compact_fingers = max(
            self._distance(points, 8, 12),
            self._distance(points, 12, 16),
            self._distance(points, 16, 20),
        ) < 0.55
        self._wrist_history.append(points[0].copy())
        outward_motion = False
        if len(self._wrist_history) >= 4:
            displacement = self._wrist_history[-1] - self._wrist_history[0]
            outward_motion = float(np.linalg.norm(displacement[:2])) > 0.18

        if hand_count >= 2:
            return "NAMASTE"
        if extended_count >= 4:
            return "THANK_YOU" if outward_motion else "HELLO"
        if thumb_up and extended_count == 0:
            return "HELP"
        if pinch_index and pinch_middle:
            return "NO"
        if fingers["index"] and fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
            return "NO"
        if extended_count == 0:
            return "YES"
        if extended_count >= 3 and not fingers["thumb"]:
            return "NAMASTE" if compact_fingers else "PLEASE"
        if fingers["index"] and not fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
            return "PLEASE"
        return "PLEASE"


class HandKeypointDetector:
    """Detect up to two hands and return true normalized 3D landmarks."""

    HAND_CONNECTIONS = (
        (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
        (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15),
        (15, 16), (0, 17), (17, 18), (18, 19), (19, 20), (5, 9), (9, 13), (13, 17)
    )

    def __init__(self, model_path: Optional[str] = None, max_num_hands: int = 2):
        import mediapipe as mp

        root = os.path.dirname(os.path.abspath(__file__))
        candidate = model_path or os.path.join(root, "hand_landmarker.task")
        if not os.path.isfile(candidate):
            raise FileNotFoundError(f"MediaPipe hand model not found: {candidate}")
        self._mp = mp
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=candidate),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=0.60,
            min_hand_presence_confidence=0.60,
            min_tracking_confidence=0.60,
        )
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.classifier = GestureClassifier()
        self._timestamp = 0

    def close(self):
        self._landmarker.close()

    def detect(self, frame: np.ndarray):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        self._timestamp = max(self._timestamp + 1, int(time.monotonic() * 1000))
        result = self._landmarker.detect_for_video(image, self._timestamp)
        hands = result.hand_landmarks or []
        gesture = self.classifier.classify(hands[0], len(hands)) if hands else None
        return hands, gesture

    def detect_and_draw_hand(self, frame: np.ndarray, min_area: int = 0):
        del min_area
        hands, gesture = self.detect(frame)
        for landmarks in hands:
            points = [(int(item.x * frame.shape[1]), int(item.y * frame.shape[0])) for item in landmarks]
            for first, second in self.HAND_CONNECTIONS:
                cv2.line(frame, points[first], points[second], (43, 214, 177), 2, cv2.LINE_AA)
            for point in points:
                cv2.circle(frame, point, 3, (255, 200, 75), -1, cv2.LINE_AA)
        return frame, len(hands), hands[0] if hands else None

    @staticmethod
    def get_hand_pose_info(keypoints) -> str:
        return "HAND DETECTED" if keypoints is not None else "WAITING FOR HAND"
