"""Capture + GCS + session management for Smart Space Management.

Combines original capture.py, storage.py and session_manager.py.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Event, Lock, Semaphore
from typing import Any

import cv2
from vision import CameraSource

logger = logging.getLogger(__name__)


class CaptureMode(str, Enum):
    INTERVAL = "interval"
    SESSION = "session"


def _new_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def _validate_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value):
        raise ValueError("session_id must contain only letters, digits, underscores and hyphens")
    return value


def _bucket_client(bucket_name: str | None):
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET is not configured; cloud capture requires a bucket")
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("Install google-cloud-storage to use cloud capture") from exc
    client = storage.Client()  # Uses configured application default credentials
    return client, client.bucket(bucket_name)


class GcsSequenceUploader:
    """Uploads numbered JPEGs asynchronously, with bounded work queue."""
    def __init__(self, settings: Any, session_id: str | None = None):
        self._settings = settings
        _, self._bucket = _bucket_client(settings.gcs_bucket)
        self.session_id = _validate_id(session_id or _new_session_id())
        self._submitted_count = 0
        self._uploaded_count = 0
        self._failed_count = 0
        self.last_error: str | None = None
        self._lock = Lock()
        self._slots = Semaphore(12)
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gcs-upload")

    @property
    def gcs_base(self) -> str:
        return f"gs://{self._settings.gcs_bucket}/{self._settings.gcs_prefix.strip('/')}/{self.session_id}"

    @property
    def frame_count(self) -> int:
        with self._lock:
            return self._uploaded_count

    @property
    def failed_count(self) -> int:
        with self._lock:
            return self._failed_count

    def _object_name(self, index: int) -> str:
        return f"{self._settings.gcs_prefix.strip('/')}/{self.session_id}/frame_{index:06d}.jpg"

    def _put(self, index: int, jpeg: bytes) -> str:
        name = self._object_name(index)
        self._bucket.blob(name).upload_from_string(jpeg, content_type="image/jpeg")
        with self._lock:
            self._uploaded_count += 1
        return name

    def upload_jpeg(self, jpeg: bytes) -> str:
        with self._lock:
            self._submitted_count += 1
            index = self._submitted_count
        return self._put(index, jpeg)

    def upload_jpeg_async(self, jpeg: bytes) -> None:
        self._slots.acquire()
        with self._lock:
            self._submitted_count += 1
            index = self._submitted_count
        try:
            self._executor.submit(self._put_safe, index, jpeg)
        except BaseException:
            self._slots.release()
            raise

    def _put_safe(self, index: int, jpeg: bytes) -> None:
        try:
            self._put(index, jpeg)
        except Exception as exc:
            with self._lock:
                self._failed_count += 1
                self.last_error = str(exc)
            logger.exception("Upload failed for frame %d", index)
        finally:
            self._slots.release()

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)


class GcsArchive:
    def __init__(self, settings: Any):
        self.settings = settings
        self.client, self.bucket = _bucket_client(settings.gcs_bucket)

    def _prefix(self) -> str:
        return self.settings.gcs_prefix.strip("/") + "/"

    def list_sessions(self) -> list[dict]:
        iterator = self.client.list_blobs(self.bucket, prefix=self._prefix(), delimiter="/")
        list(iterator)
        result = []
        for path in iterator.prefixes:
            session_id = path[len(self._prefix()):].strip("/")
            if session_id:
                result.append({"session_id": session_id, "gcs_base":
                               f"gs://{self.settings.gcs_bucket}/{self._prefix()}{session_id}"})
        result.sort(key=lambda d: d["session_id"], reverse=True)
        return result

    def list_frames(self, session_id: str, limit: int = 50) -> list[dict]:
        _validate_id(session_id)
        prefix = f"{self._prefix()}{session_id}/"
        result = []
        for blob in self.client.list_blobs(self.bucket, prefix=prefix):
            if not blob.name.lower().endswith(".jpg"):
                continue
            try:
                url = blob.generate_signed_url(expiration=3600, method="GET")
            except Exception:
                logger.debug("Could not sign %s", blob.name, exc_info=True)
                url = None
            result.append({"name": blob.name.rsplit("/", 1)[-1], "object_path": blob.name,
                           "size_bytes": blob.size,
                           "updated": blob.updated.isoformat() if blob.updated else None,
                           "url": url})
            if len(result) >= limit:
                break
        return result


def encode_frame(frame, quality: int) -> bytes:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG")
    return buffer.tobytes()


def run_capture_loop(source: CameraSource, settings: Any, mode: CaptureMode, *,
                     interval_seconds: float | None = None, session_id: str | None = None,
                     stop_event: Event | None = None,
                     uploader: GcsSequenceUploader | None = None) -> GcsSequenceUploader:
    if mode == CaptureMode.INTERVAL and (interval_seconds is None or interval_seconds <= 0):
        raise ValueError("interval mode needs interval_seconds > 0")
    if interval_seconds is not None and interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    uploader = uploader or GcsSequenceUploader(settings, session_id=session_id)
    stop_event = stop_event or Event()
    next_upload_at = 0.0
    cap = None
    try:
        cap = source.open()
        # For recorded videos, sample by video time rather than reading the whole
        # file as fast as possible and accidentally uploading only its first frame.
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        recorded = Path(source.value).is_file() and fps > 0
        frame_index = 0
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                logger.info("End of video / camera read failure")
                break
            now = frame_index / fps if recorded else time.monotonic()
            frame_index += 1
            if interval_seconds is not None and now < next_upload_at:
                continue
            if interval_seconds is not None:
                next_upload_at = now + interval_seconds
            uploader.upload_jpeg_async(encode_frame(frame, settings.jpeg_quality))
    finally:
        if cap is not None:
            cap.release()
        uploader.shutdown(wait=True)
    if uploader.failed_count:
        raise RuntimeError(f"{uploader.failed_count} frame uploads failed: {uploader.last_error}")
    return uploader


@dataclass
class SessionHandle:
    session_id: str
    source: str
    mode: CaptureMode
    interval_seconds: float | None
    gcs_base: str
    status: str = "starting"
    frame_count: int = 0
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stop_event: Event = field(default_factory=Event, repr=False)
    uploader: GcsSequenceUploader | None = field(default=None, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)

    def snapshot(self) -> dict:
        return {
            "session_id": self.session_id,
            "source": self.source,
            "mode": self.mode,
            "interval_seconds": self.interval_seconds,
            "status": self.status,
            "frame_count": self.uploader.frame_count if self.uploader else self.frame_count,
            "gcs_base": self.gcs_base,
            "started_at": self.started_at,
            "error": self.error,
        }


class SessionManager:
    def __init__(self, settings: Any):
        self.settings = settings
        self._lock = Lock()
        self._sessions: dict[str, SessionHandle] = {}

    def start(self, source: str, mode: CaptureMode, interval_seconds: float | None = None,
              session_id: str | None = None) -> SessionHandle:
        if not self.settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET must be set to start cloud capture")
        session_id = _validate_id(session_id or _new_session_id())
        handle = SessionHandle(session_id, source, mode, interval_seconds,
                               f"gs://{self.settings.gcs_bucket}/{self.settings.gcs_prefix.strip('/')}/{session_id}")
        with self._lock:
            if session_id in self._sessions:
                raise ValueError("Session ID already used (choose a new one to avoid overwriting frames)")
            self._sessions[session_id] = handle
        handle.thread = threading.Thread(target=self._run, args=(handle,), daemon=True,
                                         name=f"capture-{session_id}")
        handle.thread.start()
        return handle

    def _run(self, handle: SessionHandle) -> None:
        try:
            handle.status = "running"
            uploader = GcsSequenceUploader(self.settings, session_id=handle.session_id)
            handle.uploader = uploader
            run_capture_loop(CameraSource(handle.source), self.settings, handle.mode,
                             interval_seconds=handle.interval_seconds,
                             session_id=handle.session_id, stop_event=handle.stop_event,
                             uploader=uploader)
            handle.frame_count = uploader.frame_count
            handle.status = "stopped"
        except Exception as exc:
            logger.exception("Capture failed: %s", handle.session_id)
            handle.error = str(exc)
            handle.status = "error"

    def stop(self, session_id: str) -> SessionHandle:
        handle = self.get(session_id)
        if handle.status in {"running", "starting"}:
            handle.status = "stopping"
            handle.stop_event.set()
        return handle

    def get(self, session_id: str) -> SessionHandle:
        with self._lock:
            handle = self._sessions.get(session_id)
        if handle is None:
            raise KeyError(session_id)
        return handle

    def list_live(self) -> list[SessionHandle]:
        with self._lock:
            return list(self._sessions.values())
