import os
from fastapi.testclient import TestClient
from fastapi import FastAPI
from camera_cloud_capture.seat_monitor_v1.cv_database_api import router, get_cv_store
from camera_cloud_capture.seat_monitor_v1.publish_recorded_demo import make_payload


class FakeMongoCVStore:
    """Test double for MongoDB, not used in real server."""
    def __init__(self):
        self.saved = {}
    def write(self, doc):
        self.saved[doc['room_id']] = doc
    def read(self, room_id):
        return self.saved.get(room_id)


def sample():
    return {
      'room_id': 'demo-study-hall',
      'mode': 'RECORDED_VIDEO',
      'camera_mode': 'MOVING',
      'seat_ids_calibrated': False,
      'model_id': 'seat-analysis-8ssal/1',
      'frame_index': 0,
      'video_time_seconds': 0.0,
      'detections': [
        {'detection_label': 'D01', 'state': 'AVAILABLE', 'class_name': 'empty-chair', 'confidence': .93, 'bbox_xyxy': [1,2,100,200]},
        {'detection_label': 'D02', 'state': 'UNKNOWN', 'class_name': 'empty-chair', 'confidence': .67, 'bbox_xyxy': [30,40,130,160], 'reason': 'ambiguous'},
      ],
    }


def test_protected_demo_write_and_read(monkeypatch):
    monkeypatch.setenv('CV_INGEST_TOKEN', 'test-secret-key-long-enough')
    fake = FakeMongoCVStore()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_cv_store] = lambda: fake
    client = TestClient(app)
    assert client.post('/api/cv/ingest', json=sample()).status_code == 401
    assert client.post('/api/cv/ingest', json=sample(), headers={'X-CV-Ingest-Key': 'wrong'}).status_code == 401
    success = client.post('/api/cv/ingest', json=sample(), headers={'X-CV-Ingest-Key': 'test-secret-key-long-enough'})
    assert success.status_code == 200, success.text
    assert success.json()['stored'] is True
    assert success.json()['counts'] == {'candidate_chairs': 2, 'available': 1, 'occupied': 0, 'unknown': 1}
    saved = client.get('/api/cv/rooms/demo-study-hall')
    assert saved.status_code == 200, saved.text
    assert saved.json()['database'] == 'mongodb'
    assert saved.json()['live'] is False
    assert saved.json()['reservation_safe'] is False
    assert saved.json()['detections'][1]['state'] == 'UNKNOWN'
    assert client.get('/api/cv/rooms/h1-room-1').status_code == 404
    assert set(fake.saved) == {'demo-study-hall'}


def test_reject_unsafe_or_invalid_frames(monkeypatch):
    monkeypatch.setenv('CV_INGEST_TOKEN', 'test-secret-key-long-enough')
    fake = FakeMongoCVStore()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_cv_store] = lambda: fake
    client = TestClient(app)
    token = {'X-CV-Ingest-Key': 'test-secret-key-long-enough'}
    for key, val in [('room_id', 'h1-room-1'), ('mode', 'LIVE'), ('camera_mode', 'FIXED'), ('seat_ids_calibrated', True)]:
        invalid = {**sample(), key: val}
        assert client.post('/api/cv/ingest', json=invalid, headers=token).status_code == 422
    duplicate = sample()
    duplicate['detections'].append(dict(duplicate['detections'][0]))
    assert client.post('/api/cv/ingest', json=duplicate, headers=token).status_code == 422
    assert fake.saved == {}


def test_replay_payload_is_real_frame_local_detection():
    report = {'model_id': 'seat-analysis-8ssal/1'}
    s = {'index': 1, 'video_time_seconds': 3.1, 'detections': sample()['detections']}
    p = make_payload(report, s)
    assert p['room_id'] == 'demo-study-hall'
    assert p['camera_mode'] == 'MOVING'
    assert p['seat_ids_calibrated'] is False
    assert p['frame_index'] == 1
    assert p['detections'][0]['detection_label'] == 'D01'
