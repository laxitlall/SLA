from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from camera_cloud_capture.capture import CaptureMode

SessionStatus = Literal["starting", "running", "stopping", "stopped", "error"]


class StartSessionRequest(BaseModel):
    source: str = Field(default="0", description="Device index or stream URL")
    mode: CaptureMode = CaptureMode.INTERVAL
    interval_seconds: float | None = Field(default=2.0, gt=0)
    session_id: str | None = None


class SessionSnapshot(BaseModel):
    session_id: str
    source: str
    mode: CaptureMode
    interval_seconds: float | None
    status: SessionStatus
    frame_count: int
    gcs_base: str
    started_at: datetime
    error: str | None = None


class DeviceListResponse(BaseModel):
    devices: list[int]


class ArchiveSession(BaseModel):
    session_id: str
    gcs_base: str


class FrameItem(BaseModel):
    name: str
    object_path: str
    size_bytes: int | None
    updated: str | None
    url: str | None = None


class FrameListResponse(BaseModel):
    session_id: str
    frames: list[FrameItem]
