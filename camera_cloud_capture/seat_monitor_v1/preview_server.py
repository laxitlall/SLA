"""Use SLA's EXISTING FastAPI app plus read-only CV demo endpoints.

This changes no backend/main.py, MongoDB state or existing React routes.
Run at SLA root:
  python -m uvicorn camera_cloud_capture.seat_monitor_v1.preview_server:app --reload --host 127.0.0.1 --port 8000
"""
from backend.main import app
from camera_cloud_capture.seat_monitor_v1.cv_preview_api import router

app.include_router(router)
