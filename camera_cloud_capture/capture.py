from __future__ import annotations

import logging
import time
from enum import Enum
from threading import Event

import cv2

from camera_cloud_capture.camera import CameraSource
from camera_cloud_capture.config import Settings
from camera_cloud_capture.storage import GcsSequenceUploader

logger = logging.getLogger(__name__)


class CaptureMode(str, Enum):
    INTERVAL = "interval"
    SESSION = "session"


def encode_frame(frame, quality: int) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG")
    return buf.tobytes()


def run_capture_loop(
    source: CameraSource,
    settings: Settings,
    mode: CaptureMode,
    *,
    interval_seconds: float | None = None,
    session_id: str | None = None,
    stop_event: Event | None = None,
    uploader: GcsSequenceUploader | None = None,
) -> GcsSequenceUploader:
    """
    INTERVAL: one frame every `interval_seconds` (required).
    SESSION: capture continuously at camera rate; optional `interval_seconds` throttles uploads.
    """
    if mode == CaptureMode.INTERVAL:
        if interval_seconds is None or interval_seconds <= 0:
            raise ValueError("interval mode requires --every-seconds > 0")

    uploader = uploader or GcsSequenceUploader(settings, session_id=session_id)
    logger.info("Session %s → %s", uploader.session_id, uploader.gcs_base)

    stop_event = stop_event or Event()
    next_capture_at = time.monotonic()
    cap = source.open()
    try:
        while not stop_event.is_set():
            now = time.monotonic()
            if mode == CaptureMode.INTERVAL or (
                interval_seconds is not None and interval_seconds > 0
            ):
                if now < next_capture_at:
                    time.sleep(min(0.05, next_capture_at - now))
                    continue
                next_capture_at = now + (interval_seconds or 0)

            ok, frame = cap.read()
            if not ok:
                logger.warning("Frame read failed; stopping capture loop")
                break

            jpeg = encode_frame(frame, settings.jpeg_quality)
            uploader.upload_jpeg_async(jpeg)
    except KeyboardInterrupt:
        logger.info("Capture stopped by user")
    finally:
        cap.release()
        uploader.shutdown(wait=True)
        logger.info("Uploaded %d frame(s) in session %s", uploader.frame_count, uploader.session_id)

    return uploader
