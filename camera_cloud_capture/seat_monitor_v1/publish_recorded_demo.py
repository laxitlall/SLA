"""Publish REAL cached Roboflow model frames into MongoDB via local FastAPI.

Run: python -m camera_cloud_capture.seat_monitor_v1.publish_recorded_demo --all
This does not re-run inference; it publishes inference already saved locally.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from camera_cloud_capture.seat_monitor_v1.cv_database_api import load_settings
from camera_cloud_capture.seat_monitor_v1.cv_preview_api import normalized_samples, read_report


def make_payload(report: dict, sample: dict) -> dict:
    """Frame-local detections are NEVER mapped onto permanent S01... seats."""
    return {
        "room_id": "demo-study-hall",
        "mode": "RECORDED_VIDEO",
        "camera_mode": "MOVING",
        "seat_ids_calibrated": False,
        "model_id": report.get("model_id") or "seat-analysis-8ssal/1",
        "frame_index": sample["index"],
        "video_time_seconds": sample["video_time_seconds"],
        "detections": sample["detections"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish actual recorded CV detections into the MongoDB demo collection")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--all", action="store_true", help="Replay all recorded samples in order")
    selector.add_argument("--index", type=int, default=0, help="Publish one frame (default: 0)")
    parser.add_argument("--interval", type=float, default=2.0, help="Pause between replayed frames (seconds)")
    args = parser.parse_args()
    if not 0 <= args.interval <= 60:
        parser.error("--interval must be between 0 and 60")

    load_settings()
    token = os.getenv("CV_INGEST_TOKEN", "")
    if len(token) < 16:
        parser.error("Set a private CV_INGEST_TOKEN (16+ characters) in SLA/.env before publishing")
    report = read_report()
    samples = normalized_samples(report)
    if not samples:
        parser.error("No saved Roboflow samples found")
    selected = samples if args.all else [samples[args.index]] if 0 <= args.index < len(samples) else None
    if selected is None:
        parser.error(f"--index must be between 0 and {len(samples)-1}")
    for i, sample in enumerate(selected):
        payload = make_payload(report, sample)
        request = Request(
            "http://127.0.0.1:8001/api/cv/ingest",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-CV-Ingest-Key": token},
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                answer = json.load(response)
        except HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            parser.exit(1, f"Server rejected frame {sample['index']} (HTTP {exc.code}): {detail}\n")
        except URLError as exc:
            parser.exit(1, f"Cannot reach local CV server on 8001: {exc.reason}\n")
        print(f"Stored actual Roboflow frame {sample['index']+1}/{len(samples)} in MongoDB: {answer['counts']}")
        if args.all and i < len(selected) - 1:
            time.sleep(args.interval)
    print("Open http://localhost:5173/cv-monitor to see the MongoDB-backed observations.")
    print("No real room occupancy or RSVP records were changed.")


if __name__ == "__main__":
    main()
