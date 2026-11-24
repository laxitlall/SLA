"""Test draft seat map API with fake Mongo; no credentials, network or writes."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from camera_cloud_capture.seat_monitor_v1.cv_database_api import router as snapshots_router, get_cv_store
from camera_cloud_capture.seat_monitor_v1.cv_seat_map_api import (
    router as map_router, build_proposal, render_room_preview, DEMO_ROOM,
)


def detection(name, state, bbox, conf):
    return {"detection_label": name, "state": state, "class_name": "empty-chair",
            "bbox_xyxy": bbox, "confidence": conf}


def snap(frame_idx=0):
    return {
        "room_id": DEMO_ROOM,
        "frame_index": frame_idx,
        "video_time_seconds": frame_idx*3.0,
        "published_at": "2026-11-23T00:00:00Z",
        "detections": [
            detection("D01", "AVAILABLE", [10,10,80,100], .91),
            detection("D02", "OCCUPIED", [200,10,280,100], .88),
        ],
    }


class FakeCollection:
    def __init__(self, db):
        self.db = db
        self.docs = {}
    @property
    def database(self):
        return self.db
    def replace_one(self, q, value, upsert):
        assert upsert is True
        self.docs[q["_id"]] = dict(value)
    def find_one(self, query, projection=None):
        value = self.docs.get(query["_id"])
        if value is None:
            return None
        return {k: v for k, v in value.items() if k != "_id"} if projection else value


class FakeDB(dict):
    def __missing__(self, key):
        self[key] = FakeCollection(self)
        return self[key]


class FakeStore:
    def __init__(self):
        self.db = FakeDB()
        self.snapshots = {}
    def collection(self):
        return self.db["cv_demo_snapshots"]
    def read(self, room_id):
        return self.snapshots.get(room_id)


def raw_report():
    return {"model_id": "seat-analysis-8ssal/1", "metadata": {"width": 400, "height": 200},
            "samples": [{"video_time_seconds": 0.0, "detections": [
                {"state": "AVAILABLE", "class": "empty-chair", "confidence": .91,
                 "bbox_xyxy": [10,10,80,100]},
                {"state": "OCCUPIED", "class": "occupied-chair-front", "confidence": .88,
                 "bbox_xyxy": [200,10,280,100]},
            ]}]}


def test_draft_reference_and_camera_motion_refusal():
    from camera_cloud_capture.seat_monitor_v1.cv_preview_api import normalized_samples
    report = raw_report()
    proposal = build_proposal(normalized_samples(report)[0], report["metadata"], report["model_id"])
    assert [s["seat_id"] for s in proposal["seats"]] == ["S01", "S02"]
    assert proposal["seat_ids_calibrated"] is False
    ref = render_room_preview(proposal, snap(0))
    assert ref["counts"] == {"total": 2, "available": 1, "occupied": 1, "unknown": 0}
    assert ref["safe_for_student_occupancy"] is False
    later = render_room_preview(proposal, snap(1))
    assert later["counts"] == {"total": 2, "available": 0, "occupied": 0, "unknown": 2}
    assert all(x["reason"] == "camera_moved_no_stable_tracking" for x in later["seats"])
    # If the 1st frame's box shifts even slightly out of overlap, abstain.
    moved_same_time = snap(0)
    moved_same_time["detections"][0]["bbox_xyxy"] = [120, 120, 170, 180]
    assert render_room_preview(proposal, moved_same_time)["counts"]["unknown"] == 1


def test_api_map_persistence_and_safe_reads(monkeypatch):
    from camera_cloud_capture.seat_monitor_v1 import cv_seat_map_api as module
    monkeypatch.setenv("CV_INGEST_TOKEN", "cv-test-token-at-least-16chars")
    monkeypatch.setattr(module, "read_report", raw_report)
    fake = FakeStore()
    fake.snapshots[DEMO_ROOM] = snap(0)
    app = FastAPI()
    app.include_router(snapshots_router)
    app.include_router(map_router)
    app.dependency_overrides[get_cv_store] = lambda: fake
    client = TestClient(app)

    post = "/api/cv/rooms/demo-study-hall/propose-seat-map"
    assert client.post(post).status_code == 401
    assert client.post(post, headers={"X-CV-Ingest-Key": "wrong"}).status_code == 401
    response = client.post(post, headers={"X-CV-Ingest-Key": "cv-test-token-at-least-16chars"})
    assert response.status_code == 200, response.text
    assert response.json()["candidate_seats"] == 2
    assert response.json()["live_occupancy_modified"] is False
    assert list(fake.db["cv_demo_seat_maps"].docs) == [DEMO_ROOM]
    assert "occupancy" not in fake.db and "rsvps" not in fake.db
    saved = client.get("/api/cv/rooms/demo-study-hall/seat-map")
    assert saved.status_code == 200
    assert saved.json()["calibration_state"] == "UNVERIFIED"
    status = client.get("/api/cv/rooms/demo-study-hall/seat-preview")
    assert status.status_code == 200
    assert status.json()["counts"]["available"] == 1
    fake.snapshots[DEMO_ROOM] = snap(5)
    unknown = client.get("/api/cv/rooms/demo-study-hall/seat-preview")
    assert unknown.json()["counts"] == {"total": 2, "available": 0, "occupied": 0, "unknown": 2}
    assert client.get("/api/cv/rooms/h1-room-1/seat-preview").status_code == 404
