"""Standalone, READ-ONLY recorded-CV demo app, separate from main SLA backend.

Start from project root in a terminal:
    python -m uvicorn camera_cloud_capture.seat_monitor_v1.preview_standalone:app --host 127.0.0.1 --port 8001 --log-level info --access-log

Then open http://127.0.0.1:8001/cv-demo .
It does not load backend.main, connect to MongoDB, or update live seats/RSVP.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from camera_cloud_capture.seat_monitor_v1.cv_preview_api import router

app = FastAPI(title="SLA Recorded CV Demo (standalone)")
# Browser-only access to the read-only CV endpoints from the local Vite frontend.
# Never expose this local camera-preview server directly to the public internet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(router)

@app.get('/health')
async def health():
    return {'status': 'ok', 'mode': 'recorded-cv-demo', 'mongodb_connected': False}
