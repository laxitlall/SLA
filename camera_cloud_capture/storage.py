from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from google.cloud import storage

from camera_cloud_capture.config import Settings

logger = logging.getLogger(__name__)


class GcsSequenceUploader:
    """Uploads numbered JPEG blobs under a session prefix in GCS."""

    def __init__(self, settings: Settings, session_id: str | None = None) -> None:
        self._settings = settings
        self._client = storage.Client()
        self._bucket = self._client.bucket(settings.gcs_bucket)
        self._session_id = session_id or _new_session_id()
        self._counter = 0
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gcs-upload")

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def gcs_base(self) -> str:
        prefix = self._settings.gcs_prefix.strip("/")
        return f"gs://{self._settings.gcs_bucket}/{prefix}/{self._session_id}"

    @property
    def frame_count(self) -> int:
        return self._counter

    def _object_name(self, index: int) -> str:
        prefix = self._settings.gcs_prefix.strip("/")
        return f"{prefix}/{self._session_id}/frame_{index:06d}.jpg"

    def upload_jpeg(self, jpeg_bytes: bytes) -> str:
        self._counter += 1
        index = self._counter
        return self._put_object(index, jpeg_bytes)

    def upload_jpeg_async(self, jpeg_bytes: bytes) -> None:
        self._counter += 1
        index = self._counter
        self._executor.submit(self._put_object_safe, index, jpeg_bytes)

    def _put_object(self, index: int, jpeg_bytes: bytes) -> str:
        name = self._object_name(index)
        blob = self._bucket.blob(name)
        blob.upload_from_string(jpeg_bytes, content_type="image/jpeg")
        logger.debug("Uploaded %s (%d bytes)", name, len(jpeg_bytes))
        return name

    def _put_object_safe(self, index: int, jpeg_bytes: bytes) -> None:
        try:
            self._put_object(index, jpeg_bytes)
        except Exception:
            logger.exception("GCS upload failed for frame %d", index)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)


def _new_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class GcsArchive:
    """Read session folders and signed URLs for the frontend."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = storage.Client()
        self._bucket = self._client.bucket(settings.gcs_bucket)

    def _prefix(self) -> str:
        return self._settings.gcs_prefix.strip("/") + "/"

    def list_sessions(self) -> list[dict]:
        prefix = self._prefix()
        iterator = self._client.list_blobs(self._bucket, prefix=prefix, delimiter="/")
        list(iterator)
        sessions = []
        for folder in iterator.prefixes:
            session_id = folder[len(prefix) :].strip("/")
            if not session_id:
                continue
            sessions.append(
                {
                    "session_id": session_id,
                    "gcs_base": f"gs://{self._settings.gcs_bucket}/{prefix.rstrip('/')}/{session_id}",
                }
            )
        sessions.sort(key=lambda item: item["session_id"], reverse=True)
        return sessions

    def list_frames(self, session_id: str, limit: int = 50) -> list[dict]:
        prefix = f"{self._settings.gcs_prefix.strip('/')}/{session_id}/"
        frames: list[dict] = []
        for blob in self._client.list_blobs(self._bucket, prefix=prefix):
            if not blob.name.lower().endswith(".jpg"):
                continue
            url = None
            try:
                url = blob.generate_signed_url(expiration=3600, method="GET")
            except Exception:
                logger.debug("Could not sign URL for %s", blob.name, exc_info=True)
            frames.append(
                {
                    "name": blob.name.split("/")[-1],
                    "object_path": blob.name,
                    "size_bytes": blob.size,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "url": url,
                }
            )
            if len(frames) >= limit:
                break
        return frames
