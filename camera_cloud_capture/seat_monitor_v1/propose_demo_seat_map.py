"""Save a review-only S01... proposal based on REAL first recorded Roboflow frame.

Run from SLA root (keep local CV server running on port 8001):
  python -m camera_cloud_capture.seat_monitor_v1.propose_demo_seat_map
"""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from camera_cloud_capture.seat_monitor_v1.cv_database_api import load_settings


def main():
    load_settings()
    token = os.environ.get("CV_INGEST_TOKEN", "")
    if len(token) < 16:
        raise SystemExit("CV_INGEST_TOKEN missing; check your private SLA/.env")
    request = Request(
        "http://127.0.0.1:8001/api/cv/rooms/demo-study-hall/propose-seat-map",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json", "X-CV-Ingest-Key": token},
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = json.load(response)
    except HTTPError as err:
        raise SystemExit(f"Seat map API error HTTP {err.code}: {err.read(400).decode(errors='replace')}") from None
    except URLError:
        raise SystemExit("Cannot reach CV API at http://127.0.0.1:8001. Is Uvicorn running?") from None
    print(f"Saved {body['candidate_seats']} provisional seat candidates in MongoDB (UNVERIFIED).")
    print("View the read-only preview at http://localhost:5173/cv-monitor")
    print("No hostel occupancy or RSVP was modified.")


if __name__ == "__main__":
    main()
