"""Provisional seat-map review from six *recorded, moving-camera* Roboflow frames.

This module does NOT write student occupancy, reservations or confirmed seat maps.
It keeps a draft map in the separate `cv_demo_seat_maps` MongoDB collection.
Only the exact reference frame can have tentative detected states; subsequent
moving-camera frames are UNKNOWN for all stable seat labels by design.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import hypot
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from camera_cloud_capture.seat_monitor_v1.cv_database_api import (
    MongoCVStore, get_cv_store, require_ingest_key,
)
from camera_cloud_capture.seat_monitor_v1.cv_preview_api import read_report, normalized_samples

router = APIRouter(prefix="/api/cv", tags=["CV provisional room seat mapping"])
DEMO_ROOM = "demo-study-hall"
MAP_COLLECTION = "cv_demo_seat_maps"


def _center(box: list[float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _iou(a: list[float], b: list[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2-x1) * max(0, y2-y1)
    area_a = max(0, a[2]-a[0]) * max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0]) * max(0, b[3]-b[1])
    return intersection / max(1.0, area_a+area_b-intersection)


def build_proposal(sample: dict, frame_size: dict, model_id: str) -> dict:
    """Make a *draft* S01... map using ONLY real first-frame chair boxes."""
    width, height = int(frame_size["width"]), int(frame_size["height"])
    if width <= 0 or height <= 0:
        raise ValueError("Invalid recorded frame size")
    if sample["index"] != 0:
        raise ValueError("Seat map proposal must use reference sample 0")
    detections = sample["detections"]
    if not 1 <= len(detections) <= 100:
        raise ValueError("Reference frame has no usable chair detections")
    detections = sorted(detections, key=lambda d: _center(d["bbox_xyxy"]))
    seats = []
    for i, d in enumerate(detections, 1):
        cx, cy = _center(d["bbox_xyxy"])
        seats.append({
            "seat_id": f"S{i:02d}",
            "reference_bbox_xyxy": list(d["bbox_xyxy"]),
            "reference_anchor_norm": [round(cx/width, 6), round(cy/height, 6)],
            "source_detection_label": d["detection_label"],
            "reference_confidence": round(float(d["confidence"]), 6),
        })
    return {
        "room_id": DEMO_ROOM,
        "model_id": model_id,
        "reference_frame_index": 0,
        "reference_time_seconds": float(sample["video_time_seconds"]),
        "reference_size": {"width": width, "height": height},
        "camera_mode": "MOVING",
        "calibration_state": "UNVERIFIED",
        "seat_ids_calibrated": False,
        "live": False,
        "reservable": False,
        "source": "actual_saved_roboflow_reference_frame",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seats": seats,
        "warning": "S01... are unverified candidates from the FIRST frame, not confirmed room seats.",
    }


def render_room_preview(proposal: dict, saved_snapshot: dict) -> dict:
    """Never infer stable chair identity after camera motion.

    The first-frame reference can be reviewed against that EXACT source frame.
    Even that match is labeled a preview and is not used for actual occupancy.
    """
    ref_index = proposal["reference_frame_index"]
    camera_moved = proposal["camera_mode"] != "FIXED"
    is_reference = (
        saved_snapshot["frame_index"] == ref_index
        and abs(saved_snapshot["video_time_seconds"] - proposal["reference_time_seconds"]) < 0.05
    )
    reference_only = is_reference and camera_moved
    observations = saved_snapshot.get("detections", [])
    w = proposal["reference_size"]["width"]
    h = proposal["reference_size"]["height"]
    used: set[int] = set()
    rows = []
    for seat in proposal["seats"]:
        row = {"seat_id": seat["seat_id"], "state": "UNKNOWN", "confidence": None,
               "reason": "camera_moved_no_stable_tracking" if not reference_only else "no_unique_reference_match"}
        if reference_only:
            ref_box = seat["reference_bbox_xyxy"]
            rx, ry = _center(ref_box)
            candidates = []
            for idx, obs in enumerate(observations):
                if idx in used:
                    continue
                bbox = obs["bbox_xyxy"]
                ox, oy = _center(bbox)
                distance = hypot((ox-rx)/w, (oy-ry)/h)
                overlap = _iou(ref_box, bbox)
                if overlap >= 0.65 and distance <= 0.035:
                    candidates.append((overlap, idx, obs))
            # Refuse to guess if multiple candidate boxes could represent one seat.
            if len(candidates) == 1:
                _, idx, obs = candidates[0]
                used.add(idx)
                row["state"] = obs["state"] if obs["state"] in {"AVAILABLE", "OCCUPIED"} else "UNKNOWN"
                row["confidence"] = obs["confidence"] if row["state"] != "UNKNOWN" else None
                row["reason"] = "same_reference_frame_unverified" if row["state"] != "UNKNOWN" else "ambiguous_detection"
            elif len(candidates) > 1:
                row["reason"] = "multiple_reference_matches"
        rows.append(row)
    totals = {
        "total": len(rows),
        "available": sum(r["state"] == "AVAILABLE" for r in rows),
        "occupied": sum(r["state"] == "OCCUPIED" for r in rows),
        "unknown": sum(r["state"] == "UNKNOWN" for r in rows),
    }
    return {
        "room_id": proposal["room_id"], "source_frame_index": saved_snapshot["frame_index"],
        "video_time_seconds": saved_snapshot["video_time_seconds"],
        "source_published_at": saved_snapshot.get("published_at"),
        "reference_frame_index": ref_index, "calibration_state": "UNVERIFIED",
        "camera_mode": "MOVING", "live": False, "reservable": False,
        "seat_ids_calibrated": False, "safe_for_student_occupancy": False,
        "counts": totals, "seats": rows,
        "warning": "Reference frame states are unverified. Other frames are UNKNOWN because the camera moved. Do not use these to update hostel occupancy or RSVP.",
    }


def _map_collection(store: MongoCVStore):
    # Store uses the same team's Atlas DB but an isolated, new collection.
    return store.collection().database[MAP_COLLECTION]


@router.post("/rooms/demo-study-hall/propose-seat-map", dependencies=[Depends(require_ingest_key)])
def create_demo_seat_map(store: MongoCVStore = Depends(get_cv_store)):
    """Protected command: save the actual first-frame map as UNVERIFIED."""
    report = read_report()
    samples = normalized_samples(report)
    if not samples:
        raise HTTPException(status_code=422, detail="No saved Roboflow frames available")
    frame_size = report["metadata"]
    try:
        proposed = build_proposal(samples[0], frame_size, report.get("model_id", "unknown-model"))
        _map_collection(store).replace_one(
            {"_id": DEMO_ROOM}, {"_id": DEMO_ROOM, **proposed}, upsert=True
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="Unable to propose map from saved model frames") from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save provisional seat map") from None
    return {"stored": True, "room_id": DEMO_ROOM, "collection": MAP_COLLECTION,
            "candidate_seats": len(proposed["seats"]),
            "calibration_state": "UNVERIFIED", "live_occupancy_modified": False}


@router.get("/rooms/demo-study-hall/seat-map")
def get_demo_seat_map(store: MongoCVStore = Depends(get_cv_store)):
    try:
        result = _map_collection(store).find_one({"_id": DEMO_ROOM}, {"_id": 0})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Could not read provisional seat map") from None
    if not result:
        raise HTTPException(status_code=404, detail="No draft seat map. Run propose_demo_seat_map.py first.")
    return result


@router.get("/rooms/demo-study-hall/seat-preview")
def get_demo_seat_preview(store: MongoCVStore = Depends(get_cv_store)):
    proposal = get_demo_seat_map(store)
    saved = store.read(DEMO_ROOM)
    if saved is None:
        raise HTTPException(status_code=404, detail="No saved model frames. Run publish_recorded_demo.py first.")
    return render_room_preview(proposal, saved)
