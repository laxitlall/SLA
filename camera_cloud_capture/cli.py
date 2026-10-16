from __future__ import annotations

import logging
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from camera_cloud_capture.camera import CameraSource, list_devices
from camera_cloud_capture.capture import CaptureMode, run_capture_loop
from camera_cloud_capture.config import get_settings

app = typer.Typer(no_args_is_help=True, help="Capture camera frames and upload sequences to GCS.")
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


@app.command("list-devices")
def list_devices_cmd(
    max_index: int = typer.Option(10, help="Highest device index to probe."),
) -> None:
    """List local camera device indices that OpenCV can open."""
    devices = list_devices(max_index=max_index)
    if not devices:
        console.print("[yellow]No cameras found[/yellow] (try a stream URL with --source instead).")
        raise typer.Exit(0)
    table = Table(title="Cameras")
    table.add_column("Index")
    for d in devices:
        table.add_row(str(d))
    console.print(table)


@app.command("interval")
def interval_cmd(
    source: str = typer.Option("0", "--source", "-s", help="Device index or stream URL."),
    every_seconds: float = typer.Option(..., "--every-seconds", "-e", help="Seconds between frames."),
    session_id: Optional[str] = typer.Option(None, help="Optional fixed session folder name."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Capture one frame on a fixed interval until Ctrl+C."""
    _setup_logging(verbose)
    settings = get_settings()
    uploader = run_capture_loop(
        CameraSource(source),
        settings,
        CaptureMode.INTERVAL,
        interval_seconds=every_seconds,
        session_id=session_id,
    )
    console.print(f"[green]Done.[/green] {uploader.frame_count} frames → {uploader.gcs_base}")


@app.command("session")
def session_cmd(
    source: str = typer.Option("0", "--source", "-s", help="Device index or stream URL."),
    every_seconds: Optional[float] = typer.Option(
        None,
        "--every-seconds",
        "-e",
        help="If set, throttle uploads to this interval; otherwise upload every frame read.",
    ),
    session_id: Optional[str] = typer.Option(None, help="Optional fixed session folder name."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Manual session: run until Ctrl+C, saving a numbered image sequence."""
    _setup_logging(verbose)
    settings = get_settings()
    uploader = run_capture_loop(
        CameraSource(source),
        settings,
        CaptureMode.SESSION,
        interval_seconds=every_seconds,
        session_id=session_id,
    )
    console.print(f"[green]Done.[/green] {uploader.frame_count} frames → {uploader.gcs_base}")


<<<<<<< HEAD
=======
@app.command("detect")
def detect_cmd(
    source: str = typer.Option("0", "--source", "-s", help="Device index or stream URL."),
    method: str = typer.Option(
        "haar-face",
        "--method",
        "-m",
        help="haar-face | hog-person | motion",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Local OpenCV detection preview (q to quit). Does not upload or change capture/serve."""
    _setup_logging(verbose)
    from camera_cloud_capture.detect_loop import run_detection_preview
    from camera_cloud_capture.detection import build_detector

    detector = build_detector(method)
    console.print(f"Preview with [cyan]{detector.name}[/cyan]. Press q in the window to stop.")
    frames = run_detection_preview(CameraSource(source), detector)
    console.print(f"[green]Done.[/green] Processed {frames} frame(s).")


>>>>>>> 782382c (Updated opt-in CLI preview)
@app.command("serve")
def serve_cmd(
    host: str = typer.Option(None, help="Bind host (defaults to API_HOST)."),
    port: int = typer.Option(None, help="Bind port (defaults to API_PORT)."),
) -> None:
    """Run the FastAPI backend for the frontend."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "camera_cloud_capture.api:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    app()
