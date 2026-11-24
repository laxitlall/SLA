from fastapi import FastAPI
from camera_cloud_capture.seat_monitor_v1.cv_h15_demo import router as h15_demo_router
from camera_cloud_capture.seat_monitor_v1.cv_video_upload_api import router as cv_upload_router
from fastapi.middleware.cors import CORSMiddleware
from camera_cloud_capture.seat_monitor_v1.cv_preview_api import router
from camera_cloud_capture.seat_monitor_v1.cv_database_api import router as mongo_cv_router
from camera_cloud_capture.seat_monitor_v1.cv_seat_map_api import router as seat_map_router

app = FastAPI(title="SLA Recorded CV Demo (standalone)")
# Browser-only access to the read-only CV endpoints from the local Vite frontend.
# Never expose this local camera-preview server directly to the public internet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(cv_upload_router)
app.include_router(h15_demo_router)
app.include_router(mongo_cv_router)
app.include_router(seat_map_router)

@app.get('/health')
async def health():
    return {'status': 'ok', 'mode': 'recorded-cv-demo', 'mongo_status_endpoint': '/api/cv/db-status'}

