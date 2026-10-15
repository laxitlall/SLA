from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from camera_cloud_capture.camera import list_devices
from camera_cloud_capture.capture import CaptureMode
from camera_cloud_capture.config import Settings, get_settings
from camera_cloud_capture.schemas import (
    ArchiveSession,
    DeviceListResponse,
    FrameItem,
    FrameListResponse,
    SessionSnapshot,
    StartSessionRequest,
)
from camera_cloud_capture.session_manager import SessionManager
from camera_cloud_capture.storage import GcsArchive

manager: SessionManager | None = None
archive: GcsArchive | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global manager, archive
    settings = get_settings()
    manager = SessionManager(settings)
    archive = GcsArchive(settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Camera Cloud Capture API",
        description="HTTP and WebSocket API for the capture frontend.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/devices", response_model=DeviceListResponse)
    def devices() -> DeviceListResponse:
        return DeviceListResponse(devices=list_devices())

    @app.get("/api/sessions", response_model=list[SessionSnapshot])
    def live_sessions() -> list[SessionSnapshot]:
        assert manager is not None
        return [handle.snapshot() for handle in manager.list_live()]

    @app.post("/api/sessions", response_model=SessionSnapshot)
    def start_session(body: StartSessionRequest) -> SessionSnapshot:
        assert manager is not None
        if body.mode == CaptureMode.INTERVAL and (
            body.interval_seconds is None or body.interval_seconds <= 0
        ):
            raise HTTPException(status_code=400, detail="interval mode requires interval_seconds > 0")
        try:
            handle = manager.start(
                source=body.source,
                mode=body.mode,
                interval_seconds=body.interval_seconds,
                session_id=body.session_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return handle.snapshot()

    @app.get("/api/sessions/{session_id}", response_model=SessionSnapshot)
    def get_session(session_id: str) -> SessionSnapshot:
        assert manager is not None
        try:
            return manager.get(session_id).snapshot()
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found") from None

    @app.post("/api/sessions/{session_id}/stop", response_model=SessionSnapshot)
    def stop_session(session_id: str) -> SessionSnapshot:
        assert manager is not None
        try:
            return manager.stop(session_id).snapshot()
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found") from None

    @app.get("/api/archive/sessions", response_model=list[ArchiveSession])
    def archived_sessions() -> list[ArchiveSession]:
        assert archive is not None
        return [ArchiveSession(**item) for item in archive.list_sessions()]

    @app.get("/api/archive/sessions/{session_id}/frames", response_model=FrameListResponse)
    def archived_frames(session_id: str, limit: int = 50) -> FrameListResponse:
        assert archive is not None
        frames = [FrameItem(**item) for item in archive.list_frames(session_id, limit=limit)]
        return FrameListResponse(session_id=session_id, frames=frames)

    @app.websocket("/ws/sessions/{session_id}")
    async def session_socket(websocket: WebSocket, session_id: str) -> None:
        assert manager is not None
        await websocket.accept()
        try:
            while True:
                try:
                    payload = manager.get(session_id).snapshot()
                except KeyError:
                    await websocket.send_json({"error": "Session not found", "session_id": session_id})
                    break
                await websocket.send_json(payload.model_dump(mode="json"))
                if payload.status in ("stopped", "error"):
                    break
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            return

    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings: Settings = get_settings()
    uvicorn.run(
        "camera_cloud_capture.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
