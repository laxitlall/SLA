"""Tests for the read-only CV preview endpoints. Run from SLA root: python -m pytest camera_cloud_capture/seat_monitor_v1/test_cv_preview_api.py -q"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from camera_cloud_capture.seat_monitor_v1.cv_preview_api import router


def test_sampled_video_is_explicitly_not_live():
    client = TestClient(FastAPI())
    client.app.include_router(router)
    r = client.get('/api/cv-preview/samples')
    assert r.status_code == 200
    data = r.json()
    assert data['live'] is False
    assert data['publishable_to_live_occupancy'] is False
    assert data['reservation_safe'] is False
    assert len(data['samples']) == 6
    assert data['samples'][0]['counts']['available'] == 8
    # Same chair was labeled empty and occupied in this real frame.
    assert data['samples'][3]['counts']['ambiguous_predictions'] == 1
    assert data['samples'][3]['counts']['unknown'] == 1
    assert data['samples'][3]['counts']['occupied'] == 0


def test_annotated_frames_are_images():
    client = TestClient(FastAPI())
    client.app.include_router(router)
    assert client.get('/api/cv-preview/frame/999').status_code == 404
    r = client.get('/api/cv-preview/frame/0')
    assert r.status_code == 200
    assert r.headers['content-type'] == 'image/jpeg'
    assert r.content[:3] == b'\xff\xd8\xff'


def test_demo_webpage_is_available():
    client = TestClient(FastAPI())
    client.app.include_router(router)
    r = client.get('/cv-demo')
    assert r.status_code == 200
    assert 'RECORDED DEMO' in r.text
