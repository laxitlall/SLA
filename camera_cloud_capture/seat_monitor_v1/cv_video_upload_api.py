
from __future__ import annotations

import hmac
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from camera_cloud_capture.seat_monitor_v1.cv_database_api import get_cv_store, load_settings
from camera_cloud_capture.seat_monitor_v1.seat_status_export import clean_detections
from camera_cloud_capture.seat_monitor_v1.cv_h15_demo import AutoSeatMapper, begin_job, save_mapped_frame, mark_finished

router = APIRouter(prefix="/api/cv/demo-videos", tags=["CV admin video upload"])
HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "_outputs" / "uploaded_cv_jobs"
MAX_VIDEO_BYTES = 512 * 1024 * 1024
_jobs: dict[str, dict] = {}
_lock = threading.RLock()


def _utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require_upload_admin(x_cv_upload_password: Annotated[str | None, Header()] = None):
    load_settings()
    expected = os.getenv("CV_UPLOAD_PASSWORD", "")
    if len(expected) < 16:
        raise HTTPException(503, "Set CV_UPLOAD_PASSWORD using setup_cv_upload_password.py")
    if not x_cv_upload_password or not hmac.compare_digest(x_cv_upload_password, expected):
        raise HTTPException(401, "Admin password required")


def _set_job(job_id: str, **updates):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(updates)


def _public_job(job_id: str):
    with _lock:
        record = _jobs.get(job_id)
        if record is None:
            raise HTTPException(404, "Unknown upload job")
        # Never expose local paths, API credentials, or the original filename.
        return {key: value for key, value in record.items() if key not in {"path", "file_path"}}


def _normalize_predictions(raw: dict, width: int, height: int, threshold: float) -> list[dict]:
    """Real RF-DETR results, de-duplicated; contradictory chair labels UNKNOWN."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid Roboflow response")
    items = raw.get("predictions", [])
    if isinstance(items, dict):
        items = items.get("predictions", [])
    if not isinstance(items, list):
        raise ValueError("Invalid prediction list")
    candidates = []
    for p in items:
        if not isinstance(p, dict):
            continue
        try:
            name = str(p["class"]).strip().lower().replace("_", "-")
            if name != "empty-chair" and not name.startswith("occupied-chair"):
                continue
            confidence = float(p.get("confidence", 0))
            if not (threshold <= confidence <= 1):
                continue
            x, y, w, h = [float(p[k]) for k in ("x", "y", "width", "height")]
        except (TypeError, ValueError, KeyError):
            continue
        from math import isfinite
        if not all(map(isfinite, (x, y, w, h))) or w <= 0 or h <= 0:
            continue
        box = [max(0, int(x - w / 2)), max(0, int(y - h / 2)),
               min(width - 1, int(x + w / 2)), min(height - 1, int(y + h / 2))]
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        candidates.append({"class": name, "confidence": confidence,
                           "state": "AVAILABLE" if name == "empty-chair" else "OCCUPIED",
                           "bbox_xyxy": box})
    clean, _ = clean_detections(candidates)
    clean.sort(key=lambda p: (p["bbox_xyxy"][0], p["bbox_xyxy"][1]))
    return [{"detection_label": f"D{i:02d}", "state": p["state"],
             "class_name": p["class"], "confidence": round(float(p["confidence"]), 5),
             "bbox_xyxy": p["bbox_xyxy"], "reason": p.get("ambiguity")}
            for i, p in enumerate(clean, 1)]


def _render_frame(frame, dets: list[dict], t: float, target: Path):
    import cv2
    colors = {"AVAILABLE": (50, 170, 65), "OCCUPIED": (50, 50, 235), "UNKNOWN": (0, 195, 235)}
    output = frame.copy()
    for d in dets:
        box = [int(x) for x in d["bbox_xyxy"]]
        color = colors.get(d["state"], colors["UNKNOWN"])
        cv2.rectangle(output, tuple(box[:2]), tuple(box[2:]), color, 2)
        at = (max(box[0], 0), max(20, box[1] - 6))
        cv2.putText(output, f'{d["detection_label"]} {d["state"]}', at,
                    cv2.FONT_HERSHEY_SIMPLEX, .42, color, 2, cv2.LINE_AA)
    cv2.putText(output, f"PRERECORDED MP4 t={t:.1f}s | FRAME-LOCAL IDs",
                (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 225, 40), 2, cv2.LINE_AA)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(target), output):
        raise RuntimeError("Could not save annotated sample")



def _cv_safe_roboflow_error(error):
    """Safe diagnostics: never interpolate SDK error text, URL, headers or key."""
    code = getattr(error, "status_code", None)
    if not isinstance(code, int):
        nested = getattr(error, "inner_error", None)
        code = getattr(nested, "status_code", None) if nested is not None else None
    if isinstance(code, int):
        hints = {
            400: "Request rejected; check input image and model ID",
            401: "Unauthorized; verify ROBOFLOW_API_KEY is valid for this model",
            402: "Account payment or inference credits required",
            403: "Forbidden; verify model permissions and account credits",
            404: "Model endpoint not found; verify ROBOFLOW_MODEL_ID",
            408: "Request timed out at the provider",
            413: "Image too large; automatic downscaling is enabled",
            422: "Provider rejected the submitted image or model parameters",
            429: "Rate limit or quota reached; check Roboflow usage",
            500: "Roboflow server error; retry or check provider status",
            502: "Roboflow gateway error; retry",
            503: "Roboflow temporarily unavailable; retry",
            504: "Roboflow gateway timeout; retry",
        }
        return f"Roboflow HTTP {code}: {hints.get(code, 'Provider rejected request')}"
    if type(error).__name__ in {"HTTPServerConnectionError", "ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout"}:
        return "Roboflow connection failed or timed out; check internet/hotspot"
    return f"{type(error).__name__}: processing failed; check local Python logs"


def _cv_infer_retry(client, image_path, model_id):
    """Retries only transient provider errors; never retries invalid keys or payment failures."""
    import time
    for attempt in range(3):
        try:
            return client.infer(str(image_path), model_id=model_id)
        except Exception as error:
            status = getattr(error, "status_code", None)
            if status not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))




class _CvLocalRFDETRClient:
    """Batch18: class IDs mapped from verified fine-tuned labels, never COCO.

    A checkpoint with a 5-class head can still have default COCO label metadata.
    This adapter requires actual ordered labels from checkpoint or class_names.txt.
    """
    _EXPECTED = {
        'empty-chair', 'occupied-chair-back', 'occupied-chair-front',
        'occupied-chair-side', 'standing-person',
    }

    @classmethod
    def _verified_labels(cls, path):
        import argparse
        import os
        # Highest-priority explicit artifact next to the checkpoint.
        labels_file = path.with_name('class_names.txt')
        if labels_file.is_file():
            labels = labels_file.read_text(encoding='utf-8-sig').splitlines()
            source = 'class_names.txt'
        else:
            labels = None
            source = 'checkpoint metadata'
            try:
                import torch
                from torch.serialization import safe_globals
                # Avoid arbitrary unpickling; only allow the standard argparse
                # Namespace used by older RF-DETR training checkpoints.
                with safe_globals([argparse.Namespace]):
                    data = torch.load(str(path), map_location='cpu', weights_only=True)
                if isinstance(data, dict):
                    args = data.get('args', {})
                    labels = data.get('class_names')
                    if labels is None:
                        labels = args.get('class_names') if isinstance(args, dict) else getattr(args, 'class_names', None)
            except Exception:
                # An unsupported/unsafe checkpoint format is not a reason to
                # use COCO names. Require an explicit label sidecar instead.
                labels = None
            if labels is None:
                configured = os.getenv('CV_RFDETR_CLASS_NAMES', '').strip()
                if configured:
                    labels = configured.split(',')
                    source = 'CV_RFDETR_CLASS_NAMES'
        if not isinstance(labels, (tuple, list)):
            raise RuntimeError('RF-DETR checkpoint lacks ordered class labels. '
                               'Place a verified class_names.txt alongside weights.pt '
                               '(one class per line in training ID order).')
        labels = [str(x).strip().lower().replace('_', '-') for x in labels]
        if len(labels) != 5 or set(labels) != cls._EXPECTED:
            raise RuntimeError('RF-DETR class labels from ' + source +
                               ' do not match the five trained SLA classes. '
                               'Verify the exact dataset ID order; do not use COCO labels.')
        return labels

    def __init__(self, weights):
        from pathlib import Path
        from rfdetr import RFDETRSmall
        path = Path(weights).expanduser()
        if not path.is_file():
            raise RuntimeError('CV_LOCAL_RFDETR_WEIGHTS does not point to an existing file')
        if path.suffix.lower() not in {'.pth', '.pt', '.ckpt'}:
            raise RuntimeError('Expected a trained RF-DETR checkpoint (.pth/.pt/.ckpt)')
        self._labels = self._verified_labels(path)
        # Explicit architecture, already confirmed on the user's fine-tuned Small.
        model = RFDETRSmall(pretrain_weights=str(path), device='cpu', num_classes=5)
        self._predictor = model.inference(compile=False)

    def infer(self, image, model_id=None):
        detections = self._predictor.predict(str(image))
        if isinstance(detections, (list, tuple)):
            if len(detections) != 1:
                raise RuntimeError('Unexpected local RF-DETR batch size')
            detections = detections[0]
        boxes = detections.xyxy
        scores = detections.confidence
        ids = getattr(detections, 'class_id', None)
        if ids is None or len(ids) != len(boxes):
            raise RuntimeError('RF-DETR returned no usable numeric class IDs')
        output = []
        for i, (box, category_id) in enumerate(zip(boxes, ids)):
            category_id = int(category_id)
            # Batch20: audited legacy RF-DETR one-based chair IDs.
            # On 12 labeled test images, raw ID 1 matched empty-chair 72/74 times;
            # raw ID 3 matched occupied-chair-front 8/9 times. The checkpoint
            # uses different numeric output IDs than YOLO data.yaml.
            # 0 and 5 were not validated as physical chair classes. Skip them;
            # do not guess whether they are background or standing-person.
            if category_id in (0, len(self._labels)):
                continue
            if not 1 <= category_id < len(self._labels):
                raise RuntimeError(f'Unexpected RF-DETR class ID {category_id}. '
                                   'Check the dataset label IDs and checkpoint.')
            x1, y1, x2, y2 = (float(v) for v in box)
            score = float(scores[i]) if scores is not None else 1.0
            output.append({'class': self._labels[category_id - 1], 'confidence': score,
                           'x': (x1+x2)/2, 'y': (y1+y2)/2,
                           'width': x2-x1, 'height': y2-y1})
        return {'predictions': output}

def _process_video(job_id: str, video: Path, interval: float, max_samples: int, threshold: float):
    """Background processing. Each real Roboflow frame updates Mongo demo feed."""
    import cv2
    from inference_sdk import InferenceHTTPClient, InferenceConfiguration
    load_settings()
    key = os.getenv("ROBOFLOW_API_KEY", "")
    model_id = os.getenv("ROBOFLOW_MODEL_ID", "seat-analysis-8ssal/1")
    local_weights = os.getenv("CV_LOCAL_RFDETR_WEIGHTS", "").strip()
    if local_weights:
        client = _CvLocalRFDETRClient(local_weights)
    else:
        if not key:
            raise RuntimeError("ROBOFLOW_API_KEY not set")
        client = InferenceHTTPClient(api_url="https://serverless.roboflow.com", api_key=key)
        client = client.configure(InferenceConfiguration(api_key_transport="header"))
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError("Could not decode MP4 file")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or count <= 0:
        capture.release()
        raise RuntimeError("Video metadata is missing")
    duration = count / fps
    sample_times = [round(i * interval, 3) for i in range(min(max_samples, int(duration / interval) + 1)) if i * interval < duration]
    if not sample_times:
        capture.release()
        raise RuntimeError("Video has no samples")
    _set_job(job_id, total_samples=len(sample_times), duration_seconds=round(duration, 2))
    mapper = AutoSeatMapper(count=8)
    last_publish_at = None
    begin_job(job_id)
    directory = OUTPUT_DIR / job_id
    try:
        for index, target_time in enumerate(sample_times):
            # Recorded-video replay cadence: ~6 s if inference is faster.
            if last_publish_at is not None:
                import time
                time.sleep(max(0.0, 6.0 - (time.monotonic() - last_publish_at)))
            capture.set(cv2.CAP_PROP_POS_MSEC, target_time * 1000)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Video decoding failed at a sampled time")
            at_seconds = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000 or target_time
            h, w = frame.shape[:2]
            if max(h, w) > 1280:
                scale = 1280.0 / max(h, w)
                frame = cv2.resize(frame, (max(1, round(w * scale)), max(1, round(h * scale))),
                                   interpolation=cv2.INTER_AREA)
            image_path = directory / f"input_{index:03d}.jpg"
            directory.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(image_path), frame):
                raise RuntimeError("Could not encode sample")
            try:
                raw = _cv_infer_retry(client, image_path, model_id)
            finally:
                image_path.unlink(missing_ok=True)
            detections = _normalize_predictions(raw, frame.shape[1], frame.shape[0], threshold)
            counts = {"candidate_chairs": len(detections),
                      "available": sum(d["state"] == "AVAILABLE" for d in detections),
                      "occupied": sum(d["state"] == "OCCUPIED" for d in detections),
                      "unknown": sum(d["state"] == "UNKNOWN" for d in detections)}
            snapshot = {"room_id": "demo-study-hall", "mode": "RECORDED_VIDEO",
                        "camera_mode": "MOVING", "seat_ids_calibrated": False,
                        "model_id": model_id, "frame_index": index,
                        "video_time_seconds": float(round(at_seconds, 3)),
                        "detections": detections, "counts": counts,
                        "published_at": _utc(), "live": False,
                        "reservation_safe": False, "database": "mongodb",
                        "note": "Real uploaded video prediction. Frame-local chair IDs; no stable seat mapping."}
            get_cv_store().write(snapshot)
            save_mapped_frame(mapper, job_id, detections,
                              frame.shape[1], frame.shape[0], index, at_seconds)
            import time
            last_publish_at = time.monotonic()
            _render_frame(frame, detections, at_seconds,
                          directory / f"frame_{index:03d}.jpg")
            _set_job(job_id, finished_samples=index + 1,
                     latest_index=index, latest_counts=counts,
                     latest_time_seconds=round(at_seconds, 2))
    finally:
        capture.release()


def _worker(job_id: str, video: Path, interval: float, max_samples: int, threshold: float):
    try:
        _set_job(job_id, status="processing")
        _process_video(job_id, video, interval, max_samples, threshold)
        mark_finished(job_id, True)
        _set_job(job_id, status="complete", completed_at=_utc())
    except Exception as error:
        import traceback
        traceback.print_exc()
        try:
            mark_finished(job_id, False)
        except Exception:
            pass
        # Never return cloud SDK exceptions (could contain credentials or video paths).
        _set_job(job_id, status="failed", error=_cv_safe_roboflow_error(error))
    finally:
        video.unlink(missing_ok=True)


@router.post("/upload", dependencies=[Depends(require_upload_admin)], status_code=202)
async def upload_recorded_mp4(file: UploadFile = File(...),
                              interval_seconds: float = Form(10.0),
                              max_samples: int = Form(36),
                              confidence_threshold: float = Form(.50)):
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(422, "Select an MP4 video")
    if not 3 <= interval_seconds <= 60 or not 1 <= max_samples <= 60 or not .25 <= confidence_threshold <= .95:
        raise HTTPException(422, "Invalid sampling options")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    path = OUTPUT_DIR / f"temporary_{job_id}.mp4"
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_VIDEO_BYTES:
                    raise HTTPException(413, "MP4 exceeds the 512 MB demo limit")
                out.write(chunk)
        if size < 1024:
            raise HTTPException(422, "MP4 file is empty")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    with _lock:
        _jobs[job_id] = {"job_id": job_id, "status": "queued", "created_at": _utc(),
                         "finished_samples": 0, "total_samples": None,
                         "latest_index": None, "latest_counts": None,
                         "room_id": "demo-study-hall", "live": False,
                         "seat_ids_calibrated": False, "real_room_occupancy_modified": False}
    threading.Thread(target=_worker, args=(job_id, path, interval_seconds, max_samples, confidence_threshold),
                     daemon=True, name=f"cv-demo-{job_id[:8]}").start()
    return {"job_id": job_id, "status": "queued", "room_id": "demo-study-hall", "live": False}


@router.get("/jobs/{job_id}", dependencies=[Depends(require_upload_admin)])
def get_upload_status(job_id: str):
    return _public_job(job_id)


@router.get("/jobs/{job_id}/frames/{index}", dependencies=[Depends(require_upload_admin)])
def get_upload_frame(job_id: str, index: int):
    if not 0 <= index <= 60:
        raise HTTPException(404, "Frame unavailable")
    _public_job(job_id)
    path = OUTPUT_DIR / job_id / f"frame_{index:03d}.jpg"
    if not path.is_file():
        raise HTTPException(404, "Frame not processed yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
