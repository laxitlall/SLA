from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator

import cv2

logger = logging.getLogger(__name__)


@dataclass
class CameraSource:
    """Device index (0, 1, …) or stream URL (rtsp://, http://, file path)."""

    value: str

    def open(self) -> cv2.VideoCapture:
        if self.value.isdigit():
            cap = cv2.VideoCapture(int(self.value), cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.value)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera source: {self.value}")
        return cap


def list_devices(max_index: int = 10) -> list[int]:
    found: list[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            found.append(i)
            cap.release()
    return found


def frames(source: CameraSource) -> Iterator[tuple[bool, any]]:
    cap = source.open()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                logger.warning("Frame read failed; stopping capture loop")
                break
            yield ok, frame
    finally:
        cap.release()
