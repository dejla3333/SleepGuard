"""Facial landmark detection and eye-aspect-ratio measurement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np


@dataclass
class EyeResult:
    state: str  # "OPEN", "CLOSED", or "UNKNOWN"
    ear_left: Optional[float] = None
    ear_right: Optional[float] = None
    ear_average: Optional[float] = None
    message: str = "Face not detected"


class EyeDetector:
    """
    Uses MediaPipe Face Mesh landmarks and the standard six-point EAR formula.
    MediaPipe's `solutions.face_mesh` API is legacy upstream, but is present in
    the pinned mediapipe 0.10.21 package. It avoids a separate model download.
    """

    # Six landmark points per eye: two horizontal corners and four vertical points.
    LEFT_EYE = (362, 385, 387, 263, 373, 380)
    RIGHT_EYE = (33, 160, 158, 133, 153, 144)

    def __init__(self, threshold: float = 0.21,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5) -> None:
        self.threshold = float(threshold)
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    @staticmethod
    def _ear(landmarks, indices, width: int, height: int) -> float:
        points = np.array(
            [(landmarks[i].x * width, landmarks[i].y * height) for i in indices],
            dtype=np.float32,
        )
        # EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        vertical_a = np.linalg.norm(points[1] - points[5])
        vertical_b = np.linalg.norm(points[2] - points[4])
        horizontal = np.linalg.norm(points[0] - points[3])
        if horizontal < 1e-6:
            raise ValueError("Eye landmarks collapsed; measurement is unreliable.")
        return float((vertical_a + vertical_b) / (2.0 * horizontal))

    def process(self, frame_bgr: np.ndarray) -> tuple[EyeResult, np.ndarray]:
        """Return eye state and an annotated frame. Frame stays local to this process."""
        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._mesh.process(rgb)
        annotated = frame_bgr
        if not result.multi_face_landmarks:
            return EyeResult("UNKNOWN", message="Face not detected"), annotated

        landmarks = result.multi_face_landmarks[0].landmark
        try:
            left = self._ear(landmarks, self.LEFT_EYE, width, height)
            right = self._ear(landmarks, self.RIGHT_EYE, width, height)
        except (IndexError, ValueError, FloatingPointError) as exc:
            return EyeResult("UNKNOWN", message=f"Unreliable landmarks: {exc}"), annotated

        average = (left + right) / 2.0
        # Both eyes must be below threshold to call the state closed.
        # If either is clearly open, do not trigger a closure alarm.
        if left < self.threshold and right < self.threshold:
            state = "CLOSED"
        elif left >= self.threshold or right >= self.threshold:
            state = "OPEN"
        else:
            state = "UNKNOWN"

        # Small diagnostic overlays, not a full mesh, to keep the preview readable.
        for eye_indices, color in ((self.LEFT_EYE, (0, 220, 180)),
                                   (self.RIGHT_EYE, (0, 220, 180))):
            pts = []
            for idx in eye_indices:
                p = landmarks[idx]
                pts.append((int(p.x * width), int(p.y * height)))
            cv2.polylines(annotated, [np.array(pts, dtype=np.int32)], True, color, 1)
        return EyeResult(state, left, right, average, "Face tracked"), annotated

    def close(self) -> None:
        self._mesh.close()
