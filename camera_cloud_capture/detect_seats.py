from __future__ import annotations

from pathlib import Path
from typing import Any
import cv2
import numpy as np

# COCO class names in YOLOv11 that correspond to seat occupancy
CHAIR_CLASSES = {"chair", "couch", "bench"}
PERSON_CLASSES = {"person"}
LAPTOP_CLASSES = {"laptop"}
BAG_CLASSES = {"backpack", "handbag", "suitcase"}


def _boxes_overlap(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> bool:
    """
    Returns True if box_b overlaps significantly with box_a (or its center lies inside/near box_a).
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    # Expand chair box slightly (15%) to catch laptops/people sitting right on/above the chair
    pad_x = int((ax2 - ax1) * 0.15)
    pad_y = int((ay2 - ay1) * 0.15)
    eax1, eay1, eax2, eay2 = ax1 - pad_x, ay1 - pad_y, ax2 + pad_x, ay2 + pad_y

    inter_x1 = max(eax1, bx1)
    inter_y1 = max(eay1, by1)
    inter_x2 = min(eax2, bx2)
    inter_y2 = min(eay2, by2)

    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return False

    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    chair_area = max(1, (ax2 - ax1) * (ay2 - ay1))
    obj_area = max(1, (bx2 - bx1) * (by2 - by1))

    return (inter_area / min(chair_area, obj_area)) >= 0.15


def detect_seats_in_frame(
    frame: np.ndarray,
    *,
    seat_prefix: str = "LIB-R1",
    conf_threshold: float = 0.25,
    save_annotated_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Runs YOLOv11 on a BGR image frame, detects chairs + people + laptops + bags,
    and returns a list of seat state dictionaries ready for MongoDB Atlas & React frontend.
    """
    from ultralytics import YOLO

    model_path = Path(__file__).resolve().parent.parent / "yolo11n.pt"
    model = YOLO(str(model_path) if model_path.exists() else "yolo11n.pt")
    results = model(frame, conf=conf_threshold, verbose=False)

    chairs: list[tuple[tuple[int, int, int, int], float]] = []
    persons: list[tuple[int, int, int, int]] = []
    laptops: list[tuple[int, int, int, int]] = []
    bags: list[tuple[int, int, int, int]] = []

    for box in results[0].boxes:
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        coords = tuple(map(int, box.xyxy[0]))
        conf = float(box.conf[0])

        if class_name in CHAIR_CLASSES:
            chairs.append((coords, conf))
        elif class_name in PERSON_CLASSES:
            persons.append(coords)
        elif class_name in LAPTOP_CLASSES:
            laptops.append(coords)
        elif class_name in BAG_CLASSES:
            bags.append(coords)

    # Sort chairs left-to-right, top-to-bottom for deterministic seat numbering
    chairs.sort(key=lambda item: (item[0][1] // 80, item[0][0]))

    annotated = frame.copy()
    seats: list[dict[str, Any]] = []

    for idx, (chair_box, conf) in enumerate(chairs, start=1):
        seat_id = f"{seat_prefix}-S{idx:02d}"
        has_person = any(_boxes_overlap(chair_box, p) for p in persons)
        has_laptop = any(_boxes_overlap(chair_box, l) for l in laptops)
        has_bag = any(_boxes_overlap(chair_box, b) for b in bags)

        if has_person:
            state = "OCCUPIED"
            color = (0, 0, 255)  # Red
        elif has_laptop or has_bag:
            state = "SPOT_HELD"
            color = (0, 165, 255)  # Orange/Amber
        else:
            state = "AVAILABLE"
            color = (0, 200, 0)  # Green

        x1, y1, x2, y2 = chair_box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            f"{seat_id.split('-')[-1]}:{state[:4]} ({conf:.2f})",
            (x1, max(y1 - 8, 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )

        seats.append(
            {
                "seat_id": seat_id,
                "detections": {
                    "person": has_person,
                    "laptop": has_laptop,
                    "bag": has_bag,
                },
                "computed_state": state,
                "confidence_score": round(conf, 2),
            }
        )

    if save_annotated_path:
        out_path = Path(save_annotated_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), annotated)

    return seats


def detect_seats_from_source(
    *,
    image_path: str | None = None,
    camera_source: str | None = None,
    seat_prefix: str = "LIB-R1",
) -> list[dict[str, Any]]:
    """
    Captures a single frame from either an image file or a live camera source
    and runs YOLO seat occupancy detection.
    """
    from camera_cloud_capture.camera import CameraSource

    frame = None
    if image_path and Path(image_path).exists():
        frame = cv2.imread(image_path)
    elif camera_source is not None:
        cap = CameraSource(str(camera_source)).open()
        try:
            ok, captured = cap.read()
            if ok:
                frame = captured
        finally:
            cap.release()

    if frame is None:
        raise FileNotFoundError(
            "Could not load frame from the specified image_path or camera_source."
        )

    output_file = Path("outputs") / "detected_seats.jpg"
    return detect_seats_in_frame(
        frame, seat_prefix=seat_prefix, save_annotated_path=output_file
    )


if __name__ == "__main__":
    default_img = Path("images/room.jpeg")
    if not default_img.exists():
        print(f"Place a room image at {default_img} or call detect_seats_from_source(camera_source='0').")
    else:
        detected = detect_seats_from_source(image_path=str(default_img))
        print(f"Total seats detected: {len(detected)}")
        for s in detected:
            print(s)
