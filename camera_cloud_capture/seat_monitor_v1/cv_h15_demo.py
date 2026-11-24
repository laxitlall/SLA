"""H15 Study Room 1: eight-seat, auto-proposed fixed-view mapping for an MP4 demo.

Important: these are provisional physical seat IDs, generated from first clear
frames of a stationary camera. No writes to the team's campus occupancy or RSVP
collections. Student GET returns only seat state, never video frames.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from math import hypot
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from camera_cloud_capture.seat_monitor_v1.cv_database_api import get_cv_store
from camera_cloud_capture.seat_monitor_v1.cv_database_api import load_settings
import hmac
from typing import Annotated

router = APIRouter(prefix="/api/cv/h15-room-1", tags=["H15 recorded video seat replay"])
ROOM_ID = "h15-room-1"
COLLECTION = "cv_h15_room1_demo_states"
SEAT_IDS = [f"S{i:02d}" for i in range(1, 9)]


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def blank_seats(reason="Awaiting video calibration"):
    return [{"seat_id": sid, "state": "UNKNOWN", "confidence": None, "reason": reason} for sid in SEAT_IDS]


def state_collection():
    return get_cv_store().collection().database[COLLECTION]


def publish_state(payload: dict):
    """Only isolated H15 demo collection; never overwrite reservations."""
    state_collection().replace_one({"_id": ROOM_ID}, {"_id": ROOM_ID, **payload}, upsert=True)


def begin_job(job_id: str):
    publish_state({
        "room_id": ROOM_ID, "job_id": job_id, "status": "CALIBRATING",
        "mapping": "AUTO_PROPOSED_UNVERIFIED", "source": "RECORDED_MP4_REPLAY",
        "updated_at": utc_now(), "frame_index": None, "video_time_seconds": None,
        "seats": blank_seats(), "cadence_seconds": 6,
        "note": "Automatic reference proposals from the earliest sufficiently clear video frames",
    })


def mark_finished(job_id: str, success: bool):
    coll = state_collection()
    coll.update_one({"_id": ROOM_ID, "job_id": job_id},
                    {"$set": {"status": "FINISHED" if success else "FAILED", "updated_at": utc_now()}})


def _box(item: dict, w: int, h: int):
    try:
        a, b, c, d = (float(v) for v in item["bbox_xyxy"])
        if c <= a or d <= b or w <= 0 or h <= 0:
            return None
        return (a / w, b / h, c / w, d / h)
    except (KeyError, ValueError, TypeError):
        return None


def _iou(a, b):
    overlap = max(0., min(a[2], b[2]) - max(a[0], b[0])) * max(0., min(a[3], b[3]) - max(a[1], b[1]))
    area_a = (a[2] - a[0]) * (a[3] - a[1]); area_b = (b[2] - b[0]) * (b[3] - b[1])
    return overlap / (area_a + area_b - overlap) if area_a + area_b > overlap else 0.


def _distance(a, b):
    return hypot((a[0]+a[2]-b[0]-b[2])/2, (a[1]+a[3]-b[1]-b[3])/2)


class AutoSeatMapper:
    """Find first eight distinct chair locations; freeze anchors for later frames.

    It does not pretend that panning camera tracking works. Unmatched/ambiguous
    detection -> UNKNOWN; label numbers are stable within one fixed-view video.
    """

    def __init__(self, count: int = 8):
        self.count = count
        self.candidates = []
        self.anchors = None
        self.frames_seen = 0

    def _detect(self, detections, width, height):
        out = []
        for det in detections:
            box = _box(det, width, height)
            if box is None:
                continue
            if det.get("state") not in {"AVAILABLE", "OCCUPIED", "UNKNOWN"}:
                continue
            out.append({"bbox": box, "state": det["state"],
                        "confidence": float(det.get("confidence") or 0)})
        return out

    def map_frame(self, detections: list[dict], width: int, height: int):
        self.frames_seen += 1
        found = self._detect(detections, width, height)
        if self.anchors is None:
            # A clear full first frame is the preferred automatic reference.
            if len(found) >= self.count:
                ranked = sorted(found, key=lambda f: f["confidence"], reverse=True)[:self.count]
                self.anchors = [f["bbox"] for f in sorted(ranked, key=lambda f: ((f["bbox"][0] + f["bbox"][2])/2, (f["bbox"][1] + f["bbox"][3])/2))]
            else:
                # Accumulate unique locations across initial stationary frames.
                for f in sorted(found, key=lambda f: f["confidence"], reverse=True):
                    if any(_iou(f["bbox"], a) >= .42 or _distance(f["bbox"], a) < .04 for a in self.candidates):
                        continue
                    self.candidates.append(f["bbox"])
                    if len(self.candidates) >= self.count:
                        self.anchors = sorted(self.candidates[:self.count], key=lambda a: ((a[0]+a[2])/2,(a[1]+a[3])/2))
                        break
        if self.anchors is None:
            return blank_seats(f"Calibrating: {min(len(self.candidates),self.count)}/{self.count} chair positions found"), False

        options = []
        for idx, anchor in enumerate(self.anchors):
            for j, det in enumerate(found):
                overlap = _iou(anchor, det["bbox"])
                dist = _distance(anchor, det["bbox"])
                if overlap >= .24 and dist <= .12:
                    score = overlap + max(0, .12-dist) * .7
                    options.append((score, idx, j))
        options.sort(reverse=True)
        assignment = {}
        claimed = set()
        for score, idx, j in options:
            if idx not in assignment and j not in claimed:
                assignment[idx] = j
                claimed.add(j)
        seats = []
        for idx, sid in enumerate(SEAT_IDS):
            if idx not in assignment:
                seats.append({"seat_id": sid, "state": "UNKNOWN", "confidence": None,
                              "reason": "No unambiguous detection at the anchored seat position"})
            else:
                det = found[assignment[idx]]
                # An overlapping contradictory chair label is already marked
                # UNKNOWN by clean_detections in cv_video_upload_api.py.
                seats.append({"seat_id": sid, "state": det["state"],
                              "confidence": round(det["confidence"], 4),
                              "reason": "matched_fixed_reference" if det["state"] != "UNKNOWN" else "contradictory_detection"})
        return seats, True


def save_mapped_frame(mapper: AutoSeatMapper, job_id: str, detections: list[dict],
                      width: int, height: int, index: int, video_time: float):
    seats, ready = mapper.map_frame(detections, width, height)
    payload = {"room_id": ROOM_ID, "job_id": job_id,
               "status": "REPLAYING" if ready else "CALIBRATING",
               "mapping": "AUTO_PROPOSED_UNVERIFIED", "source": "RECORDED_MP4_REPLAY",
               "updated_at": utc_now(), "frame_index": index,
               "video_time_seconds": round(float(video_time), 2),
               "seats": seats, "cadence_seconds": 6,
               "note": "Stationary-camera auto-mapping preview; verify physical chair IDs before deployment"}
    publish_state(payload)
    return payload


@router.get("/seat-status")
def get_h15_seat_status():
    try:
        doc = state_collection().find_one({"_id": ROOM_ID}, {"_id": 0})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "H15 seat feed could not reach MongoDB") from None
    if doc is None:
        return {"room_id": ROOM_ID, "status": "NO_VIDEO", "mapping": "NOT_CONFIGURED",
                "source": "RECORDED_MP4_REPLAY", "cadence_seconds": 6,
                "seats": blank_seats(), "frame_index": None, "updated_at": None}
    return doc

def check_h15_admin(x_cv_upload_password: Annotated[str | None, Header()] = None):
    load_settings()
    expected = os.getenv("CV_UPLOAD_PASSWORD", "")
    if len(expected) < 16:
        raise HTTPException(503, "Configure CV upload admin password first")
    if not x_cv_upload_password or not hmac.compare_digest(expected, x_cv_upload_password):
        raise HTTPException(401, "Admin authorization required")


@router.post("/admin-check", dependencies=[Depends(check_h15_admin)])
def admin_check():
    return {"authenticated": True}
