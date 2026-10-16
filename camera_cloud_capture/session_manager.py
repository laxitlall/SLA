from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from camera_cloud_capture.camera import CameraSource
from camera_cloud_capture.capture import CaptureMode, run_capture_loop
from camera_cloud_capture.config import Settings
from camera_cloud_capture.schemas import SessionSnapshot, SessionStatus
from camera_cloud_capture.storage import GcsSequenceUploader, _new_session_id

logger = logging.getLogger(__name__)


class SessionHandle:
    def __init__(
        self,
        *,
        session_id: str,
        source: str,
        mode: CaptureMode,
        interval_seconds: float | None,
        gcs_base: str,
    ) -> None:
        self.session_id = session_id
        self.source = source
        self.mode = mode
        self.interval_seconds = interval_seconds
        self.gcs_base = gcs_base
        self.status: SessionStatus = "starting"
        self.frame_count = 0
        self.error: str | None = None
        self.started_at = datetime.now(timezone.utc)
        self.stop_event = threading.Event()
        self.uploader: GcsSequenceUploader | None = None
        self.thread: threading.Thread | None = None

    def snapshot(self) -> SessionSnapshot:
        if self.uploader is not None:
            self.frame_count = self.uploader.frame_count
        return SessionSnapshot(
            session_id=self.session_id,
            source=self.source,
            mode=self.mode,
            interval_seconds=self.interval_seconds,
            status=self.status,
            frame_count=self.frame_count,
            gcs_base=self.gcs_base,
            started_at=self.started_at,
            error=self.error,
        )


class SessionManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionHandle] = {}

    def start(
        self,
        *,
        source: str,
        mode: CaptureMode,
        interval_seconds: float | None,
        session_id: str | None,
    ) -> SessionHandle:
        session_id = session_id or _new_session_id()
        prefix = self._settings.gcs_prefix.strip("/")
        gcs_base = f"gs://{self._settings.gcs_bucket}/{prefix}/{session_id}"
        handle = SessionHandle(
            session_id=session_id,
            source=source,
            mode=mode,
            interval_seconds=interval_seconds,
            gcs_base=gcs_base,
        )
        with self._lock:
            if session_id in self._sessions and self._sessions[session_id].status in (
                "starting",
                "running",
            ):
                raise ValueError(f"Session {session_id} is already running")
            self._sessions[session_id] = handle

        thread = threading.Thread(
            target=self._run,
            args=(handle,),
            name=f"capture-{session_id}",
            daemon=True,
        )
        handle.thread = thread
        thread.start()
        return handle

    def _run(self, handle: SessionHandle) -> None:
        handle.status = "running"
        try:
            handle.uploader = GcsSequenceUploader(self._settings, session_id=handle.session_id)
            uploader = run_capture_loop(
                CameraSource(handle.source),
                self._settings,
                handle.mode,
                interval_seconds=handle.interval_seconds,
                session_id=handle.session_id,
                stop_event=handle.stop_event,
                uploader=handle.uploader,
            )
            handle.frame_count = uploader.frame_count
            handle.status = "stopped"
        except Exception as exc:
            logger.exception("Capture session %s failed", handle.session_id)
            handle.error = str(exc)
            handle.status = "error"

    def stop(self, session_id: str) -> SessionHandle:
        handle = self.get(session_id)
        if handle.status in ("running", "starting"):
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
