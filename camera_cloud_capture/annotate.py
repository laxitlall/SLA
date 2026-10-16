from __future__ import annotations

import cv2
import numpy as np

from camera_cloud_capture.boxes import BoundingBox


def draw_boxes(frame: np.ndarray, boxes: list[BoundingBox]) -> np.ndarray:
    """Return a copy of `frame` with labeled rectangles. Does not mutate the original."""
    overlay = frame.copy()
    for box in boxes:
        x1, y1, x2, y2 = box.as_xyxy
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 220, 80), 2)
        caption = f"{box.label} {box.score:.2f}"
        cv2.putText(
            overlay,
            caption,
            (x1, max(16, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 220, 80),
            1,
            cv2.LINE_AA,
        )
    return overlay
