"""Read-only FastAPI preview of real Roboflow sampled video detections.

This module NEVER POSTs occupancy, updates MongoDB, or supplies reservable seat IDs.
Run with: python -m uvicorn camera_cloud_capture.seat_monitor_v1.preview_server:app --reload --port 8000
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from camera_cloud_capture.seat_monitor_v1.seat_status_export import clean_detections

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE / '_outputs'
REPORT = OUTPUTS / 'video_detection_report.json'
VIDEO = OUTPUTS / 'source' / 'hall_recorded_sample.mp4'
DASHBOARD = HERE / 'cv_demo_dashboard.html'

router = APIRouter(tags=['CV Recorded Demo'])


def read_report() -> dict[str, Any]:
    if not REPORT.is_file():
        raise HTTPException(status_code=404, detail=f'Roboflow report missing: {REPORT}. Run video_roboflow_demo.py infer first.')
    try:
        value = json.loads(REPORT.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail='Roboflow report is not valid JSON') from exc
    if not isinstance(value, dict) or not value.get('samples') or not isinstance(value.get('metadata'), dict):
        raise HTTPException(status_code=422, detail='Roboflow report is missing samples or metadata')
    return value


def normalized_samples(report: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for sample in report['samples']:
        cleaned, ambiguities = clean_detections(sample.get('detections', []))
        # D01, D02... are detection numbers *within this frame*, not persistent seat IDs.
        cleaned.sort(key=lambda d: (d['bbox_xyxy'][0], d['bbox_xyxy'][1]))
        detections = []
        for i, det in enumerate(cleaned, 1):
            state = det['state'] if det['state'] in ('AVAILABLE', 'OCCUPIED') else 'UNKNOWN'
            detections.append({
                'detection_label': f'D{i:02d}',
                'state': state,
                'class_name': det['class'],
                'confidence': float(det['confidence']),
                'bbox_xyxy': list(det['bbox_xyxy']),
                'reason': det.get('ambiguity'),
            })
        out.append({
            'index': len(out),
            'video_time_seconds': float(sample['video_time_seconds']),
            'counts': {
                'candidate_chairs': len(detections),
                'available': sum(d['state'] == 'AVAILABLE' for d in detections),
                'occupied': sum(d['state'] == 'OCCUPIED' for d in detections),
                'unknown': sum(d['state'] == 'UNKNOWN' for d in detections),
                'ambiguous_predictions': ambiguities,
            },
            'detections': detections,
        })
    return out


@router.get('/api/cv-preview/samples')
def get_preview_samples():
    """Actual Roboflow inference results, safe for displaying to students/admins as recorded demo ONLY."""
    report = read_report()
    return {
        'room_id': report.get('room_id', 'demo-study-hall'),
        'model_id': report.get('model_id'),
        'mode': 'RECORDED_VIDEO',
        'camera_mode': 'MOVING',
        'live': False,
        'seat_ids_calibrated': False,
        'reservation_safe': False,
        'publishable_to_live_occupancy': False,
        'note': 'Chair detections belong to individual frames, not stable physical seats. No MongoDB/RSVP updates.',
        'frame_size': {k: report['metadata'][k] for k in ('width', 'height')},
        'samples': normalized_samples(report),
    }


@router.get('/api/cv-preview/frame/{index}')
def get_annotated_frame(index: int):
    report = read_report()
    samples = normalized_samples(report)
    if not 0 <= index < len(samples):
        raise HTTPException(status_code=404, detail='Sample index does not exist')
    if not VIDEO.is_file():
        raise HTTPException(status_code=404, detail=f'Recorded video is missing: {VIDEO}')
    try:
        import cv2
    except ImportError as exc:
        raise HTTPException(status_code=503, detail='opencv-python is required') from exc

    capture = cv2.VideoCapture(str(VIDEO))
    if not capture.isOpened():
        raise HTTPException(status_code=422, detail='Unable to open recorded video')
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, samples[index]['video_time_seconds'] * 1000)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok:
        raise HTTPException(status_code=422, detail='Unable to decode video frame')
    h, w = frame.shape[:2]
    size = report['metadata']
    if (w, h) != (int(size['width']), int(size['height'])):
        raise HTTPException(status_code=409, detail='Video frame size does not match inference report; boxes would be incorrect')

    color = {'AVAILABLE': (60, 174, 51), 'OCCUPIED': (68, 67, 230), 'UNKNOWN': (13, 195, 244)}
    for det in samples[index]['detections']:
        x1, y1, x2, y2 = map(int, det['bbox_xyxy'])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        co = color[det['state']]
        cv2.rectangle(frame, (x1, y1), (x2, y2), co, 2)
        label = f"{det['detection_label']} {det['state']} {det['confidence']:.0%}"
        scale = .49
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        tx = min(max(0, x1), max(0, w - text_w - 8))
        ty = max(text_h + 6, min(y1 - 4, h - 3))
        cv2.rectangle(frame, (tx, ty - text_h - 4), (tx + text_w + 7, ty + 4), co, -1)
        cv2.putText(frame, label, (tx + 3, ty), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.rectangle(frame, (0, 0), (min(w - 1, 520), 28), (22, 32, 39), -1)
    cv2.putText(frame, f"RECORDED ROBOFLOW | t={samples[index]['video_time_seconds']:.1f}s | NOT LIVE", (7, 19),
                cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1, cv2.LINE_AA)
    ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise HTTPException(status_code=500, detail='Could not generate annotated frame')
    return Response(content=encoded.tobytes(), media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


@router.get('/cv-demo', response_class=HTMLResponse)
def cv_demo():
    if not DASHBOARD.is_file():
        raise HTTPException(status_code=404, detail='Preview HTML is missing')
    return HTMLResponse(DASHBOARD.read_text(encoding='utf-8'))
