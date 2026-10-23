"""FastAPI + Pydantic contracts + Typer CLI for Smart Space Management.

Combines original api.py, schemas.py, config.py and cli.py. Run:
    uvicorn server:app --reload
    python server.py --help
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import typer
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console
from rich.table import Table

from capture import CaptureMode, GcsArchive, SessionManager, run_capture_loop
from vision import (CameraSource, analyze_occupancy, build_detector, detect_chairs,
                    list_devices, run_detection_preview)

logger = logging.getLogger(__name__)
console = Console()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    gcs_bucket: str | None = None  # Optional for health, local CV and API startup
    gcs_prefix: str = "captures"
    jpeg_quality: int = Field(default=90, ge=1, le=100)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    occupancy_api_key: str | None = None  # Set before exposing ingestion outside localhost

    @property
    def cors_origin_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


SessionStatus = Literal["starting", "running", "stopping", "stopped", "error"]


class StartSessionRequest(BaseModel):
    source: str = "0"
    mode: CaptureMode = CaptureMode.INTERVAL
    interval_seconds: float | None = Field(default=2.0, gt=0)
    session_id: str | None = None

    @model_validator(mode="after")
    def check_interval(self):
        if self.mode == CaptureMode.INTERVAL and self.interval_seconds is None:
            raise ValueError("interval mode requires interval_seconds")
        return self


class SessionSnapshot(BaseModel):
    session_id: str
    source: str
    mode: CaptureMode
    interval_seconds: float | None
    status: SessionStatus
    frame_count: int
    gcs_base: str
    started_at: datetime
    error: str | None = None


class DeviceListResponse(BaseModel):
    devices: list[int]


class ArchiveSession(BaseModel):
    session_id: str
    gcs_base: str


class FrameItem(BaseModel):
    name: str
    object_path: str
    size_bytes: int | None
    updated: str | None
    url: str | None = None


class FrameListResponse(BaseModel):
    session_id: str
    frames: list[FrameItem]


class SeatStatus(BaseModel):
    seat_id: str = Field(min_length=1)
    status: Literal["occupied", "available", "unknown"]
    confidence: float | None = Field(default=None, ge=0, le=1)


class Counts(BaseModel):
    total: int = Field(ge=0)
    occupied: int = Field(ge=0)
    available: int = Field(ge=0)
    unknown: int = Field(ge=0)


class OccupancySnapshot(BaseModel):
    room_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    observed_at: datetime
    frame_index: int | None = Field(default=None, ge=0)
    counts: Counts
    seats: list[SeatStatus]

    @model_validator(mode="after")
    def validate_counts(self):
        values = [s.seat_id for s in self.seats]
        if len(values) != len(set(values)):
            raise ValueError("duplicate seat IDs")
        counts = self.counts
        if counts.total != len(self.seats) or counts.total != counts.occupied+counts.available+counts.unknown:
            raise ValueError("counts do not equal seat records")
        for status in ("occupied", "available", "unknown"):
            if getattr(counts, status) != sum(s.status == status for s in self.seats):
                raise ValueError(f"inconsistent count for {status}")
        return self


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    manager = SessionManager(settings)
    # In-memory data, intentionally not a replacement for MongoDB persistence.
    latest: dict[str, OccupancySnapshot] = {}
    app = FastAPI(title="Smart Space Capture + Occupancy API", version="0.2.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/devices", response_model=DeviceListResponse)
    def devices():
        return DeviceListResponse(devices=list_devices())

    @app.get("/api/sessions", response_model=list[SessionSnapshot])
    def sessions():
        return [s.snapshot() for s in manager.list_live()]

    @app.post("/api/sessions", response_model=SessionSnapshot)
    def start_session(body: StartSessionRequest):
        try:
            return manager.start(source=body.source, mode=body.mode,
                                 interval_seconds=body.interval_seconds,
                                 session_id=body.session_id).snapshot()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}", response_model=SessionSnapshot)
    def get_session(session_id: str):
        try:
            return manager.get(session_id).snapshot()
        except KeyError:
            raise HTTPException(404, "Session not found") from None

    @app.post("/api/sessions/{session_id}/stop", response_model=SessionSnapshot)
    def stop_session(session_id: str):
        try:
            return manager.stop(session_id).snapshot()
        except KeyError:
            raise HTTPException(404, "Session not found") from None

    @app.websocket("/ws/sessions/{session_id}")
    async def session_socket(ws: WebSocket, session_id: str):
        await ws.accept()
        try:
            while True:
                try:
                    payload = manager.get(session_id).snapshot()
                except KeyError:
                    await ws.send_json({"error": "Session not found", "session_id": session_id})
                    break
                await ws.send_json(SessionSnapshot.model_validate(payload).model_dump(mode="json"))
                if payload["status"] in {"stopped", "error"}:
                    break
                await asyncio.sleep(.5)
        except WebSocketDisconnect:
            return

    def cloud_archive() -> GcsArchive:
        try:
            return GcsArchive(settings)
        except Exception as exc:
            logger.warning("Could not access GCS archive: %s", exc)
            raise HTTPException(503, detail=f"Cloud archive unavailable: {exc}") from exc

    @app.get("/api/archive/sessions", response_model=list[ArchiveSession])
    def archive_sessions():
        try:
            return [ArchiveSession(**item) for item in cloud_archive().list_sessions()]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, detail=f"GCS request failed: {exc}") from exc

    @app.get("/api/archive/sessions/{session_id}/frames", response_model=FrameListResponse)
    def archive_frames(session_id: str, limit: int = Query(50, ge=1, le=500)):
        try:
            items = cloud_archive().list_frames(session_id, limit=limit)
            return FrameListResponse(session_id=session_id, frames=[FrameItem(**i) for i in items])
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, detail=f"GCS request failed: {exc}") from exc

    @app.post("/api/occupancy", response_model=OccupancySnapshot)
    def set_occupancy(body: OccupancySnapshot, x_api_key: str | None = Header(default=None)):
        if settings.occupancy_api_key and x_api_key != settings.occupancy_api_key:
            raise HTTPException(401, "Invalid API key")
        existing = latest.get(body.room_id)
        if existing and body.observed_at < existing.observed_at:
            raise HTTPException(409, "Out-of-order occupancy observation")
        latest[body.room_id] = body
        return body

    @app.get("/api/occupancy", response_model=list[OccupancySnapshot])
    def all_occupancy():
        return list(latest.values())

    @app.get("/api/occupancy/{room_id}", response_model=OccupancySnapshot)
    def room_occupancy(room_id: str):
        if room_id not in latest:
            raise HTTPException(404, "No occupancy observations for this room")
        return latest[room_id]

    @app.websocket("/ws/occupancy/{room_id}")
    async def occupancy_socket(ws: WebSocket, room_id: str):
        await ws.accept()
        try:
            last_payload = None
            while True:
                snap = latest.get(room_id)
                if snap is not None:
                    payload = snap.model_dump(mode="json")
                    if payload != last_payload:
                        await ws.send_json(payload)
                        last_payload = payload
                await asyncio.sleep(.5)
        except WebSocketDisconnect:
            return

    return app


app = create_app()
cli = typer.Typer(no_args_is_help=True, help="Camera cloud capture, classic CV and YOLO occupancy")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")


@cli.command("list-devices")
def list_devices_cmd(max_index: int = typer.Option(10, help="Probe camera indexes [0,max_index)")):
    devices = list_devices(max_index)
    if not devices:
        console.print("[yellow]No local cameras found. Try a video file or URL.[/yellow]")
        return
    table = Table(title="Cameras")
    table.add_column("Index")
    for device in devices:
        table.add_row(str(device))
    console.print(table)


@cli.command("interval")
def interval_cmd(source: str = typer.Option("0", "--source", "-s"),
                 every_seconds: float = typer.Option(..., "--every-seconds", "-e"),
                 session_id: str | None = typer.Option(None), verbose: bool = False):
    setup_logging(verbose)
    sender = run_capture_loop(CameraSource(source), get_settings(), CaptureMode.INTERVAL,
                              interval_seconds=every_seconds, session_id=session_id)
    console.print(f"Uploaded {sender.frame_count} JPEGs to {sender.gcs_base}")


@cli.command("session")
def session_cmd(source: str = typer.Option("0", "--source", "-s"),
                every_seconds: float | None = typer.Option(None, "--every-seconds", "-e"),
                session_id: str | None = typer.Option(None), verbose: bool = False):
    setup_logging(verbose)
    sender = run_capture_loop(CameraSource(source), get_settings(), CaptureMode.SESSION,
                              interval_seconds=every_seconds, session_id=session_id)
    console.print(f"Uploaded {sender.frame_count} JPEGs to {sender.gcs_base}")


@cli.command("detect")
def detect_cmd(source: str = typer.Option("0", "--source", "-s"),
               method: str = typer.Option("haar-face", "--method", "-m"), verbose: bool = False):
    setup_logging(verbose)
    detector = build_detector(method)
    console.print(f"Preview {detector.name} — press q to stop")
    count = run_detection_preview(CameraSource(source), detector)
    console.print(f"Processed {count} frames")


@cli.command("detect-seats")
def detect_seats_cmd(source: str = typer.Option(..., "--source"),
                     output_dir: str = typer.Option("outputs", "--output-dir"),
                     weights: str = "yolo11n.pt", show: bool = False):
    """Detect visible chairs (original prototype); NOT occupancy."""
    result = detect_chairs(source, output_dir, weights, display=show)
    console.print(f"Visible chairs: {result['detected_chairs']} (not occupancy)")


@cli.command("occupancy")
def occupancy_cmd(source: str = typer.Option(..., "--source"),
                  seats: str = typer.Option(..., "--seats"),
                  output_dir: str = typer.Option("outputs", "--output-dir"),
                  weights: str = "yolo11n.pt", every: int = 1,
                  max_frames: int = 0, room_id: str = "room-1", camera_id: str = "camera-1",
                  api_url: str | None = typer.Option(None, help="Optional full POST URL for /api/occupancy"),
                  api_key: str | None = typer.Option(None, help="API key for X-API-Key when configured")):
    """Fixed seat regions + YOLO person detection -> occupancy JSON."""
    result = analyze_occupancy(source, seats, output_dir=output_dir, weights=weights,
                               every=every, max_frames=max_frames, room_id=room_id,
                               camera_id=camera_id, api_url=api_url, api_key=api_key)
    console.print(f"Result: {result['counts']}  Saved to {Path(output_dir) / 'latest.json'}")


@cli.command("serve")
def serve_cmd(host: str | None = typer.Option(None), port: int | None = typer.Option(None)):
    settings = get_settings()
    uvicorn.run("server:app", host=host or settings.api_host,
                port=port or settings.api_port, reload=False)


if __name__ == "__main__":
    cli()
