"""Offline API tests. Run: python -m pytest camera_cloud_capture/seat_monitor_v1/test_cv_video_upload_api.py -q"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from camera_cloud_capture.seat_monitor_v1 import cv_video_upload_api as api


def test_dedupe_real_shape_and_ambiguity():
    raw = {"predictions": [
        {"class": "empty-chair", "confidence": .78, "x": 50, "y": 50, "width": 40, "height": 40},
        {"class": "occupied-chair-front", "confidence": .69, "x": 50, "y": 50, "width": 40, "height": 40},
        {"class": "empty-chair", "confidence": .92, "x": 100, "y": 100, "width": 30, "height": 30},
        {"class": "standing-person", "confidence": .99, "x": 130, "y": 130, "width": 30, "height": 30},
    ]}
    rows = api._normalize_predictions(raw, 200, 200, .5)
    assert len(rows) == 2
    assert [r['state'] for r in rows] == ['UNKNOWN', 'AVAILABLE']
    assert [r['detection_label'] for r in rows] == ['D01','D02']


def test_admin_upload_authorization_and_job(monkeypatch, tmp_path):
    monkeypatch.setenv('CV_UPLOAD_PASSWORD', 'this-is-a-very-long-secret')
    monkeypatch.setattr(api, 'OUTPUT_DIR', tmp_path)
    monkeypatch.setattr(api, '_worker', lambda *args: None)
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    data = {"file": ("sample.mp4", b"0"*2048, "video/mp4")}
    assert client.post('/api/cv/demo-videos/upload', files=data).status_code == 401
    bad = client.post('/api/cv/demo-videos/upload', headers={'X-CV-Upload-Password': 'wrong'}, files=data)
    assert bad.status_code == 401
    resp = client.post('/api/cv/demo-videos/upload', headers={'X-CV-Upload-Password': 'this-is-a-very-long-secret'}, files=data)
    assert resp.status_code == 202, resp.text
    job = resp.json()['job_id']
    assert client.get(f'/api/cv/demo-videos/jobs/{job}').status_code == 401
    status = client.get(f'/api/cv/demo-videos/jobs/{job}', headers={'X-CV-Upload-Password':'this-is-a-very-long-secret'})
    assert status.status_code == 200 and status.json()['room_id'] == 'demo-study-hall'
    assert status.json()['real_room_occupancy_modified'] is False
    assert client.get(f'/api/cv/demo-videos/jobs/{job}/frames/0', headers={'X-CV-Upload-Password':'this-is-a-very-long-secret'}).status_code == 404


def test_install_is_repeat_safe(tmp_path):
    from install_cv_upload_batch13 import plan_install
    base = tmp_path/'camera_cloud_capture/seat_monitor_v1'
    base.mkdir(parents=True)
    frontend = tmp_path/'frontend/src/pages'
    frontend.mkdir(parents=True)
    comp = tmp_path/'frontend/src/components'
    comp.mkdir(parents=True)
    (base/'cv_video_upload_api.py').write_text('x')
    (comp/'CvVideoUploader.jsx').write_text('x')
    (base/'preview_standalone.py').write_text('from fastapi import FastAPI\nfrom camera_cloud_capture.seat_monitor_v1.cv_preview_api import router\napp = FastAPI()\napp.include_router(router)\n')
    (frontend/'CvMonitoring.jsx').write_text('import CvDemoPanel from "../components/CvDemoPanel";\nreturn (\n        <CvDemoPanel />\n)')
    changes = plan_install(tmp_path)
    assert len(changes) == 2
    for path, _, new in changes:
        path.write_text(new)
    assert plan_install(tmp_path) == []


def test_background_pipeline_uses_real_decoded_frames_with_mocked_cloud(monkeypatch, tmp_path):
    import sys
    import types
    import cv2
    import numpy as np
    monkeypatch.setenv('ROBOFLOW_API_KEY', 'dummy-for-offline-test')
    monkeypatch.setenv('ROBOFLOW_MODEL_ID', 'seat-analysis-8ssal/1')
    monkeypatch.setattr(api, 'OUTPUT_DIR', tmp_path/'output')
    class MockClient:
        calls = 0
        def __init__(self, **kwargs): pass
        def configure(self, config): return self
        def infer(self, path, model_id):
            assert Path(path).is_file()
            assert model_id == 'seat-analysis-8ssal/1'
            self.calls += 1
            return {'predictions': [{'class': 'empty-chair', 'confidence': .92,
                                     'x': 50, 'y': 50, 'width': 40, 'height': 40}]}
    class MockConfig:
        def __init__(self, **kwargs): pass
    monkeypatch.setitem(sys.modules, 'inference_sdk', types.SimpleNamespace(InferenceHTTPClient=MockClient,InferenceConfiguration=MockConfig))
    class MockMongoStore:
        def __init__(self): self.written = []
        def write(self, record): self.written.append(record)
    store=MockMongoStore()
    monkeypatch.setattr(api, 'get_cv_store', lambda: store)
    p=tmp_path/'video.mp4'
    vw=cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*'mp4v'), 2, (160,120))
    assert vw.isOpened()
    for _ in range(5):
        vw.write(np.zeros((120,160,3), dtype='uint8'))
    vw.release()
    job='offline-test'
    api._jobs[job] = {'job_id':job, 'status':'processing'}
    api._process_video(job, p, 1, 3, .5)
    assert len(store.written) == 3
    assert all(r['room_id'] == 'demo-study-hall' and r['seat_ids_calibrated'] is False for r in store.written)
    assert all(r['counts']['available'] == 1 for r in store.written)
    assert (tmp_path/'output'/job/'frame_000.jpg').is_file()
