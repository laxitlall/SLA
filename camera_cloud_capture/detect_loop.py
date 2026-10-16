from __future__ import annotations

import logging
from threading import Event

import cv2

from camera_cloud_capture.annotate import draw_boxes
from camera_cloud_capture.camera import CameraSource
from camera_cloud_capture.detection import FrameDetector

logger = logging.getLogger(__name__)


def run_detection_preview(
    source: CameraSource,
    detector: FrameDetector,
    *,
    window_name: str = "detection",
    stop_event: Event | None = None,
) -> int:
    """
    Local preview only: read frames, draw boxes, show a window.

    Does not upload to GCS and is not used by interval/session/serve.
    """
    stop_event = stop_event or Event()
    cap = source.open()
    frames = 0
    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                logger.warning("Frame read failed; stopping detection preview")
                break
            boxes = detector.detect(frame)
            preview = draw_boxes(frame, boxes)
            frames += 1
            cv2.imshow(window_name, preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        logger.info("Detection preview stopped by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return frames
