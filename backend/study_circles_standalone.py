"""Run with: python -m uvicorn backend.study_circles_standalone:app --port 8002"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .study_circles_api import router

app = FastAPI(title="Study Circles demo booking API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(router)

@app.get("/api/study-circles/health")
def health():
    return {"service": "study-circles", "status": "running", "mongo_required_for_bookings": True}
