# Smart Space — Compact Camera & Occupancy Backend

This is a **5-file** refactor of the supplied camera backend: **3 Python files + `requirements.txt` + this README**.
Original user files are not changed. This is a standalone layout; do **not** mix it with the old modules without updating their imports.

## Contents

| File | Includes (previous files) |
| --- | --- |
| `vision.py` | `camera.py`, `boxes.py`, `annotate.py`, `detection.py`, `detect_loop.py`, `detect_seats.py`; plus region-based occupancy |
| `capture.py` | `capture.py`, `storage.py`, `session_manager.py` |
| `server.py` | `api.py`, `schemas.py`, `config.py`, `cli.py` |
| `requirements.txt` | Python dependencies (not provided in original upload) |
| `README.md` | Instructions, compatibility and behavior |

### 1. Install (Python 3.11 or 3.12 recommended)

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

WSL/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For local preview `detect` you only need OpenCV; YOLO model weights are downloaded on first inference. Google Cloud credentials are only needed when using upload/archive operations.

### 2. Test the REST API (no GCS setup required)

```bash
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

- `http://127.0.0.1:8000/docs`
- `GET /api/health`
- `GET /api/devices`
- `GET /api/sessions`
- `POST /api/sessions`, `GET /api/sessions/{id}`, `POST /api/sessions/{id}/stop`
- `GET /api/archive/sessions`, `GET /api/archive/sessions/{id}/frames`
- `WS /ws/sessions/{id}`
- `POST /api/occupancy`, `GET /api/occupancy`, `GET /api/occupancy/{room_id}`
- `WS /ws/occupancy/{room_id}`

**Important:** New occupancy API data is held in RAM; restart loses it. This is not MongoDB persistence. Only the cloud archive stores JPEG files in GCS.

### 3. Classic preview detectors (preserved)

```bash
python server.py detect --source 0 --method haar-face
python server.py detect --source samples/room.mp4 --method hog-person
python server.py detect --source samples/room.mp4 --method motion
```

Press `q` to close. Displays a GUI; don't use in a headless server.

### 4. Original experimental automatic chair detector (preserved)

```bash
python server.py detect-seats --source samples/room.jpeg --output-dir outputs
```

Creates `outputs/detected_seats.jpg` and `outputs/detected_chairs.json`.
**It detects visible chairs, NOT reliable study-room seat capacity, and NOT occupied/free seats.**

### 5. Actual seat occupancy (new integration)

Reuse your existing `seats.json` from a fixed camera view, e.g.:

```json
{
  "reference_width": 1280,
  "reference_height": 720,
  "seats": [
    {"id": "S01", "box": [40, 120, 210, 390]},
    {"id": "S02", "box": [250, 110, 410, 385]}
  ]
}
```

These coordinates are example values only. If your existing JSON uses a different layout, translate it to this layout once. The region should include where a seated person's upper body appears.

Process a photograph:

```bash
python server.py occupancy --source samples/room.jpeg --seats seats.json --output-dir outputs
```

Process every 10th frame of a video:

```bash
python server.py occupancy --source samples/room.mp4 --seats seats.json --every 10 --max-frames 50
```

To upload snapshots to the local FastAPI occupancy endpoint as analysis runs (run server in another terminal):

```bash
python server.py occupancy --source samples/room.mp4 --seats seats.json --every 10 --api-url http://127.0.0.1:8000/api/occupancy
```

If the API is protected, also pass `--api-key YOUR_KEY`.

Results:
- `outputs/latest.json`: most recent occupancy estimate
- `outputs/frames.jsonl`: history for analyzed frames
- `outputs/preview.jpg`: last analyzed frame with seat annotations

This occupancy algorithm is a **heuristic**: match YOLO persons to user-defined seat regions by torso anchor or overlap. It is not trained seat classification or stable multi-frame tracking. `available` currently means **no person was matched**. Occlusion, bags and passers-by can cause errors. Same physical seats require the same camera view/calibration.

### 6. Cloud capture / session API (preserved)

Configure the environment (do not commit secrets):

```text
GCS_BUCKET=your-google-cloud-bucket
GCS_PREFIX=captures
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
CORS_ORIGINS=http://localhost:5173
API_HOST=127.0.0.1
API_PORT=8000
# Optional when accepting CV reports beyond localhost:
OCCUPANCY_API_KEY=choose-a-strong-secret
```

Run continuous capture to GCS:

```bash
python server.py session --source 0
python server.py interval --source 0 --every-seconds 2
```

Run the API with `python server.py serve`. If `OCCUPANCY_API_KEY` is configured, POST /api/occupancy requires the `X-API-Key` header. Pass `--api-key YOUR_KEY` to the `occupancy` CLI if `OCCUPANCY_API_KEY` is configured. Do not put credentials in source code or commit them.

**Security note:** Keep capture endpoints bound to localhost until proper authentication, rate limiting and camera-source allowlisting are added. They can open arbitrary local devices and URLs if publicly exposed. Do not send unprotected raw library video to users.

### 7. What changed in the consolidation

- Fixed original `cli.py` Git merge markers, which caused SyntaxError.
- Made OpenCV device backend portable (Windows DSHOW; Linux/WSL default capture).
- Made GCS lazy/optional for local CV and API health checks; cloud features still need credentials.
- Preserved capture modes, GCS sequence uploads/archive, session management, all existing API and WebSocket routes, three classic detectors, original chair-count concept and GUI preview.
- Added JSON output for the chair detector and optional fixed-region YOLO occupancy/ingestion.
- Constrained upload work queue, distinguished successful uploads from attempts, and reported failures.
- Kept source images/frames out of database responses; kept occupancy observations in memory for this prototype.
- **Entry points changed:** old `camera_cloud_capture.api:app` -> `server:app`; old `python -m camera_cloud_capture.cli` -> `python server.py <command>`. Update any startup scripts accordingly.
- Unrelated root `package.json` and `package-lock.json` belong to the JavaScript frontend and are deliberately **not** folded into this Python backend.
- Uploaded `ad` is a Git configuration dump, not application code; it has been **excluded** from the archive to avoid disclosing personal repository settings.

No camera, Google Cloud account or real study-room footage was supplied for execution. Unit/API and static checks may pass without guaranteeing model accuracy or cloud operation.
