from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np

from camera_cloud_capture.boxes import BoundingBox


class FrameDetector(ABC):
    """Optional CV pass. Capture/upload does not use this unless you call it explicitly."""

    name: str

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        raise NotImplementedError


class HaarFaceDetector(FrameDetector):
    """Classic Haar cascade faces (ships with OpenCV, no extra weights)."""

    name = "haar-face"

    def __init__(self, scale_factor: float = 1.1, min_neighbors: int = 5) -> None:
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(str(cascade_path))
        if self._cascade.empty():
            raise RuntimeError(f"Could not load Haar cascade at {cascade_path}")
        self._scale_factor = scale_factor
        self._min_neighbors = min_neighbors

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hits = self._cascade.detectMultiScale(
            gray,
            scaleFactor=self._scale_factor,
            minNeighbors=self._min_neighbors,
        )
        return [
            BoundingBox(int(x), int(y), int(w), int(h), label="face", score=1.0)
            for x, y, w, h in hits
        ]


class HogPersonDetector(FrameDetector):
    """OpenCV HOG + SVM pedestrian detector."""

    name = "hog-person"

    def __init__(self, hit_threshold: float = 0.0) -> None:
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self._hit_threshold = hit_threshold

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        rects, weights = self._hog.detectMultiScale(
            frame,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
            hitThreshold=self._hit_threshold,
        )
        boxes: list[BoundingBox] = []
        for (x, y, w, h), score in zip(rects, weights):
            boxes.append(
                BoundingBox(int(x), int(y), int(w), int(h), label="person", score=float(score))
            )
        return boxes


class MotionDetector(FrameDetector):
    """Frame-to-frame motion via grayscale absolute difference."""

    name = "motion"

    def __init__(self, min_area: int = 800, threshold: int = 25) -> None:
        self._prev_gray: np.ndarray | None = None
        self._min_area = min_area
        self._threshold = threshold

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self._prev_gray is None:
            self._prev_gray = gray
            return []
        delta = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray
        _, mask = cv2.threshold(delta, self._threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.dilate(mask, None, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: list[BoundingBox] = []
        for contour in contours:
            if cv2.contourArea(contour) < self._min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            boxes.append(BoundingBox(x, y, w, h, label="motion", score=1.0))
        return boxes


DETECTORS: dict[str, type[FrameDetector]] = {
    HaarFaceDetector.name: HaarFaceDetector,
    HogPersonDetector.name: HogPersonDetector,
    MotionDetector.name: MotionDetector,
}


def build_detector(name: str) -> FrameDetector:
    cls = DETECTORS.get(name)
    if cls is None:
        known = ", ".join(sorted(DETECTORS))
        raise ValueError(f"Unknown detector {name!r}. Choose one of: {known}")
    return cls()
