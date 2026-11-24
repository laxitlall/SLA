"""Safe, *demo-only* MongoDB bridge for real recorded Roboflow observations.

This service deliberately NEVER modifies the live `occupancy` or RSVP collections.
D01... are frame-local detection numbers, NOT permanent S01... seat identifiers.
Only localhost CLI publishing can POST; browser UI uses read-only GET.
"""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
router = APIRouter(prefix="/api/cv", tags=["Recorded CV MongoDB demo"])


def load_settings() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # Explicit shell env wins; these files must stay private and gitignored.
    for env in [ROOT / ".env", ROOT / "backend" / ".env",
                ROOT / "backend" / "database" / "atlas-credentials.env"]:
        if env.is_file():
            load_dotenv(env, override=False)


class Detection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_label: str = Field(pattern=r"^D\d{2,4}$")
    state: Literal["AVAILABLE", "OCCUPIED", "UNKNOWN"]
    class_name: str = Field(min_length=1, max_length=64)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    bbox_xyxy: list[float] = Field(min_length=4, max_length=4)
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def valid_bbox(self):
        from math import isfinite
        x1, y1, x2, y2 = self.bbox_xyxy
        if not all(isfinite(x) for x in self.bbox_xyxy) or x1 >= x2 or y1 >= y2:
            raise ValueError("Invalid bounding box")
        return self


class DemoSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    room_id: Literal["demo-study-hall"]
    mode: Literal["RECORDED_VIDEO"]
    camera_mode: Literal["MOVING"]
    seat_ids_calibrated: Literal[False]
    model_id: str = Field(min_length=3, max_length=100)
    frame_index: int = Field(ge=0, le=1000000)
    video_time_seconds: float = Field(ge=0, le=86400, allow_inf_nan=False)
    detections: list[Detection] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_frame_labels(self):
        labels = [d.detection_label for d in self.detections]
        if len(labels) != len(set(labels)):
            raise ValueError("Duplicate detection labels in the same frame")
        return self


def counts(detections: list[Detection]) -> dict:
    return {
        "candidate_chairs": len(detections),
        "available": sum(d.state == "AVAILABLE" for d in detections),
        "occupied": sum(d.state == "OCCUPIED" for d in detections),
        "unknown": sum(d.state == "UNKNOWN" for d in detections),
    }


class MongoCVStore:
    """Lazy MongoDB connection. Separate collection; no access to RSVP/occupancy."""

    def __init__(self):
        load_settings()
        self.uri = os.getenv("MONGODB_URI", "").strip()
        self.db_name = os.getenv("MONGODB_DB_NAME", "studyspot").strip() or "studyspot"
        self._client = None
        self._collection = None

    def collection(self):
        if not self.uri or "<username>" in self.uri:
            raise HTTPException(status_code=503, detail="MONGODB_URI is not configured. No database write occurred.")
        try:
            if self._collection is None:
                from pymongo import MongoClient
                client = MongoClient(
                    self.uri, serverSelectionTimeoutMS=2500,
                    connectTimeoutMS=2500, socketTimeoutMS=2500,
                )
                client.admin.command("ping")
                self._client = client
                self._collection = client[self.db_name]["cv_demo_snapshots"]
            return self._collection
        except ImportError:
            raise HTTPException(status_code=503, detail="Install pymongo to use MongoDB.") from None
        except Exception:
            # Do not reveal the connection string, host, or credentials in HTTP errors.
            self._collection = None
            raise HTTPException(status_code=503, detail="MongoDB is unreachable; verify Atlas connectivity and credentials.") from None

    def write(self, record: dict) -> None:
        try:
            self.collection().replace_one({"_id": record["room_id"]},
                                          {"_id": record["room_id"], **record}, upsert=True)
        except HTTPException:
            raise
        except Exception:
            self._collection = None
            raise HTTPException(status_code=503, detail="MongoDB write failed.") from None

    def read(self, room_id: str) -> dict | None:
        try:
            return self.collection().find_one({"_id": room_id}, {"_id": 0})
        except HTTPException:
            raise
        except Exception:
            self._collection = None
            raise HTTPException(status_code=503, detail="MongoDB read failed.") from None


@lru_cache(maxsize=1)
def get_cv_store() -> MongoCVStore:
    return MongoCVStore()


def require_ingest_key(x_cv_ingest_key: Annotated[str | None, Header()] = None):
    load_settings()
    expected = os.getenv("CV_INGEST_TOKEN", "")
    if len(expected) < 16:
        raise HTTPException(status_code=503, detail="CV_INGEST_TOKEN must be configured (16+ characters).")
    if not x_cv_ingest_key or not hmac.compare_digest(x_cv_ingest_key, expected):
        raise HTTPException(status_code=401, detail="Invalid CV ingestion key.")


@router.post("/ingest")
def ingest_demo_snapshot(
    payload: DemoSnapshot,
    _auth: None = Depends(require_ingest_key),
    store: MongoCVStore = Depends(get_cv_store),
):
    """Authenticated, demo-only MongoDB write. No student seat status updated."""
    saved = {
        **payload.model_dump(),
        "counts": counts(payload.detections),
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "live": False,
        "reservation_safe": False,
        "database": "mongodb",
        "note": "Recorded Roboflow frame, moving camera; detection IDs are not permanent seats.",
    }
    store.write(saved)
    return {"stored": True, "room_id": payload.room_id,
            "frame_index": payload.frame_index, "counts": saved["counts"],
            "database": "mongodb", "live": False}


@router.get("/rooms/{room_id}")
def get_cv_demo_room(room_id: str, store: MongoCVStore = Depends(get_cv_store)):
    if room_id != "demo-study-hall":
        raise HTTPException(status_code=404, detail="Only the isolated demo room is enabled.")
    saved = store.read(room_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="No CV frames published to MongoDB yet.")
    return saved


@router.get("/db-status")
def db_status(store: MongoCVStore = Depends(get_cv_store)):
    """Read-only status. Never expose URI or credentials."""
    try:
        store.collection()
        connected = True
    except HTTPException:
        connected = False
    load_settings()
    return {"mongodb_connected": connected,
            "ingest_token_configured": len(os.getenv("CV_INGEST_TOKEN", "")) >= 16,
            "collection": "cv_demo_snapshots",
            "live_seats_modified": False}
