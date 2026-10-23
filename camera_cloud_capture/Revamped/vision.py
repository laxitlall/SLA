"""Computer vision + camera handling for Smart Space Management.

Combines original camera.py, boxes.py, annotate.py, detection.py,
detect_loop.py and detect_seats.py. YOLO is imported only when required.
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any, Iterator

import cv2
import numpy as np

logger = logging.getLogger(__name__)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    label: str
    score: float = 1.0

    @property
    def as_xyxy(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.width, self.y + self.height


def draw_boxes(frame: np.ndarray, boxes: list[BoundingBox]) -> np.ndarray:
    result = frame.copy()
    for box in boxes:
        x1, y1, x2, y2 = box.as_xyxy
        cv2.rectangle(result, (x1, y1), (x2, y2), (0, 220, 80), 2)
        cv2.putText(result, f"{box.label} {box.score:.2f}", (x1, max(16, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 220, 80), 1, cv2.LINE_AA)
    return result


@dataclass(frozen=True)
class CameraSource:
    """Camera index, file path, or RTSP/HTTP URL."""
    value: str

    def open(self) -> cv2.VideoCapture:
        if self.value.isdigit():
            backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
            cap = cv2.VideoCapture(int(self.value), backend)
        else:
            cap = cv2.VideoCapture(self.value)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Could not open camera/video source: {self.value}")
        return cap


def list_devices(max_index: int = 10) -> list[int]:
    result = []
    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, backend)
        if cap.isOpened():
            result.append(idx)
        cap.release()
    return result


def frames(source: CameraSource) -> Iterator[tuple[bool, np.ndarray]]:
    cap = source.open()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield ok, frame
    finally:
        cap.release()


class FrameDetector(ABC):
    name: str

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[BoundingBox]: ...


class HaarFaceDetector(FrameDetector):
    name = "haar-face"

    def __init__(self, scale_factor: float = 1.1, min_neighbors: int = 5):
        path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(str(path))
        if self.cascade.empty():
            raise RuntimeError(f"Failed to load Haar cascade: {path}")
        self.scale_factor, self.min_neighbors = scale_factor, min_neighbors

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hits = self.cascade.detectMultiScale(gray, scaleFactor=self.scale_factor,
                                             minNeighbors=self.min_neighbors)
        return [BoundingBox(int(x), int(y), int(w), int(h), "face") for x, y, w, h in hits]


class HogPersonDetector(FrameDetector):
    name = "hog-person"

    def __init__(self, hit_threshold: float = 0.0):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.hit_threshold = hit_threshold

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        rects, weights = self.hog.detectMultiScale(frame, winStride=(8, 8),
                         padding=(8, 8), scale=1.05, hitThreshold=self.hit_threshold)
        return [BoundingBox(int(x), int(y), int(w), int(h), "person", float(s))
                for (x, y, w, h), s in zip(rects, weights)]


class MotionDetector(FrameDetector):
    name = "motion"

    def __init__(self, min_area: int = 800, threshold: int = 25):
        self.previous: np.ndarray | None = None
        self.min_area, self.threshold = min_area, threshold

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)
        if self.previous is None:
            self.previous = gray
            return []
        delta = cv2.absdiff(self.previous, gray)
        self.previous = gray
        _, mask = cv2.threshold(delta, self.threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.dilate(mask, None, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result = []
        for contour in contours:
            if cv2.contourArea(contour) >= self.min_area:
                x, y, w, h = cv2.boundingRect(contour)
                result.append(BoundingBox(x, y, w, h, "motion"))
        return result


_DETECTORS = {d.name: d for d in (HaarFaceDetector, HogPersonDetector, MotionDetector)}


def build_detector(method: str) -> FrameDetector:
    if method not in _DETECTORS:
        raise ValueError(f"Unknown method {method!r}. Choose: {', '.join(_DETECTORS)}")
    return _DETECTORS[method]()


def run_detection_preview(source: CameraSource, detector: FrameDetector,
                          window_name: str = "detection", stop_event: Event | None = None) -> int:
    stop_event = stop_event or Event()
    count = 0
    cap = source.open()
    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                break
            cv2.imshow(window_name, draw_boxes(frame, detector.detect(frame)))
            count += 1
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return count


def _yolo(weights: str):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install optional YOLO dependency: pip install ultralytics") from exc
    return YOLO(weights)


def detect_chairs(image_path: str, output_dir: str = "outputs", weights: str = "yolo11n.pt",
                  conf: float = .25, display: bool = False) -> dict[str, Any]:
    """Original YOLO-chair prototype, enhanced to write machine-readable JSON.

    Warning: detects visible chairs, not actual occupied/available study seats.
    """
    frame = cv2.imread(image_path)
    if frame is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    model = _yolo(weights)
    pred = model.predict(frame, conf=conf, verbose=False)[0]
    found = []
    boxes = []
    for box in pred.boxes:
        cls = int(box.cls[0])
        if str(model.names[cls]).lower() != "chair":
            continue
        seat_id = f"S{len(found)+1:02d}"
        x1, y1, x2, y2 = (int(x) for x in box.xyxy[0].tolist())
        score = float(box.conf[0])
        found.append({"seat_id": seat_id, "box": [x1, y1, x2, y2], "confidence": score})
        boxes.append(BoundingBox(x1, y1, x2-x1, y2-y1, seat_id, score))
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path / "detected_seats.jpg"), draw_boxes(frame, boxes))
    result = {"source": image_path, "detected_chairs": len(found), "chairs": found,
              "note": "Visible-chair count only; not occupancy or permanent seat capacity."}
    (path / "detected_chairs.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if display:
        cv2.imshow("Automatic Chair Detection", draw_boxes(frame, boxes))
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return result


def load_seats(filename: str) -> tuple[list[dict], tuple[int, int] | None]:
    """Load saved regions: {seats: [{id/seat_id, box/bbox: [x1,y1,x2,y2]}]}.

    Also accepts x/y/width/height and reference_width/reference_height if present.
    """
    raw = json.loads(Path(filename).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        entries, meta = raw, {}
    elif isinstance(raw, dict) and isinstance(raw.get("seats"), list):
        entries, meta = raw["seats"], raw
    else:
        raise ValueError("seats.json must contain an array named 'seats'")
    regions, seen = [], set()
    for i, item in enumerate(entries, 1):
        seat_id = str(item.get("seat_id") or item.get("id") or f"S{i:02d}")
        if seat_id in seen:
            raise ValueError(f"Duplicate seat_id: {seat_id}")
        seen.add(seat_id)
        values = item.get("box", item.get("bbox"))
        if values is None and all(k in item for k in ("x", "y", "width", "height")):
            x, y, w, h = (item[k] for k in ("x", "y", "width", "height"))
            values = [x, y, x + w, y + h]
        if not isinstance(values, list) or len(values) != 4:
            raise ValueError(f"{seat_id}: expected box: [x1,y1,x2,y2]")
        x1, y1, x2, y2 = map(int, values)
        if min(x1, y1) < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError(f"{seat_id}: invalid box coordinates {values}")
        regions.append({"seat_id": seat_id, "box": [x1, y1, x2, y2]})
    if not regions:
        raise ValueError("No seats configured")
    w = meta.get("reference_width") or meta.get("image_width")
    h = meta.get("reference_height") or meta.get("image_height")
    size = (int(w), int(h)) if w and h else None
    return regions, size


def _intersection(a: list[int], b: list[int]) -> int:
    return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))


def match_people_to_seats(seats: list[dict], people: list[dict], threshold: float = .30) -> list[dict]:
    """Greedy unique person-seat matching; frame-by-frame heuristic, not tracking.

    Uses torso/body anchor or overlap fraction of seat's calibration region.
    """
    candidates = []
    for si, seat in enumerate(seats):
        box = seat["box"]
        seat_area = max(1, (box[2]-box[0])*(box[3]-box[1]))
        for pi, person in enumerate(people):
            p = person["box"]
            anchor = ((p[0]+p[2])/2, p[1] + .65*(p[3]-p[1]))
            inside = box[0] <= anchor[0] <= box[2] and box[1] <= anchor[1] <= box[3]
            overlap = _intersection(box, p)/seat_area
            if inside or overlap >= threshold:
                candidates.append((int(inside), overlap, person["confidence"], si, pi))
    used_seats, used_people = set(), set()
    statuses = {seat["seat_id"]: {"seat_id": seat["seat_id"], "status": "available",
                                   "confidence": None} for seat in seats}
    for inside, overlap, confidence, si, pi in sorted(candidates, reverse=True):
        if si in used_seats or pi in used_people:
            continue
        used_seats.add(si)
        used_people.add(pi)
        statuses[seats[si]["seat_id"]] = {"seat_id": seats[si]["seat_id"],
                                          "status": "occupied", "confidence": float(confidence)}
    return list(statuses.values())


def analyze_occupancy(source: str, seats_path: str, *, output_dir: str = "outputs",
                      weights: str = "yolo11n.pt", conf: float = .25, every: int = 1,
                      max_frames: int = 0, room_id: str = "room-1", camera_id: str = "camera-1",
                      api_url: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    """Detect people, reuse fixed seat regions and emit occupancy JSON/preview.

    api_url is optional full URL to POST /api/occupancy. 'available' means
    no person matched this frame, and is an estimate rather than certainty.
    """
    if every < 1 or max_frames < 0 or not 0 <= conf <= 1:
        raise ValueError("every must be >= 1, max_frames >= 0, confidence in [0,1]")
    seats, ref_size = load_seats(seats_path)
    model = _yolo(weights)
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    is_image = Path(source).suffix.lower() in IMAGE_SUFFIXES
    if is_image:
        image = cv2.imread(source)
        if image is None:
            raise FileNotFoundError(source)
        frame_iter = iter([image])
        cap = None
    else:
        cap = CameraSource(source).open()
        def read_frames():
            while True:
                ok, frame = cap.read()
                if not ok:
                    return
                yield frame
        frame_iter = read_frames()

    previous = None
    count = 0
    try:
        history_path = dest / "frames.jsonl"
        with history_path.open("w", encoding="utf-8") as history:
            for frame_index, frame in enumerate(frame_iter):
                if frame_index % every:
                    continue
                h, w = frame.shape[:2]
                scaled = [dict(seat, box=([round(seat["box"][j] * (w/ref_size[0] if j%2==0 else h/ref_size[1]))
                                                 for j in range(4)] if ref_size else seat["box"])) for seat in seats]
                pred = model.predict(frame, conf=conf, classes=[0], verbose=False)[0]
                persons = []
                for item in pred.boxes:
                    x1, y1, x2, y2 = (int(v) for v in item.xyxy[0].tolist())
                    persons.append({"box": [x1, y1, x2, y2], "confidence": float(item.conf[0])})
                statuses = match_people_to_seats(scaled, persons)
                occupied = sum(s["status"] == "occupied" for s in statuses)
                previous = {
                    "room_id": room_id, "camera_id": camera_id,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "frame_index": frame_index,
                    "counts": {"total": len(statuses), "occupied": occupied,
                               "available": len(statuses)-occupied, "unknown": 0},
                    "seats": statuses,
                }
                (dest / "latest.json").write_text(json.dumps(previous, indent=2), encoding="utf-8")
                history.write(json.dumps(previous) + "\n")
                history.flush()
                overlay = frame.copy()
                for seat, status in zip(scaled, statuses):
                    x1, y1, x2, y2 = seat["box"]
                    color = (0, 175, 0) if status["status"] == "available" else (20, 20, 230)
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(overlay, f'{status["seat_id"]}: {status["status"]}',
                                (x1, max(18, y1-5)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
                cv2.imwrite(str(dest / "preview.jpg"), overlay)
                if api_url:
                    from urllib.request import Request, urlopen
                    body = json.dumps(previous).encode("utf-8")
                    headers = {"Content-Type": "application/json"}
                    if api_key:
                        headers["X-API-Key"] = api_key
                    req = Request(api_url, data=body, headers=headers, method="POST")
                    try:
                        with urlopen(req, timeout=5) as response:
                            if response.status >= 300:
                                raise RuntimeError(f"API returned {response.status}")
                    except Exception:
                        logger.exception("Could not send occupancy to API %s", api_url)
                count += 1
                print(f"Frame {frame_index}: {occupied}/{len(statuses)} occupied")
                if max_frames and count >= max_frames:
                    break
    finally:
        if cap is not None:
            cap.release()
    if previous is None:
        raise RuntimeError("No frames were analyzed")
    return previous
