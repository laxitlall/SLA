"""SLA Batch 3: REAL seat detection on selected video frames using your RF-DETR.

This is a diagnostic demo, NOT permanent seat-ID tracking. The supplied video
has camera motion. A stable seat map requires a stationary camera and review.

Commands from SLA root:
    python camera_cloud_capture/seat_monitor_v1/video_roboflow_demo.py inspect
    python camera_cloud_capture/seat_monitor_v1/video_roboflow_demo.py infer

The second command uploads sampled frames to your Roboflow inference endpoint.
No MongoDB/frontend writes; no credentials are stored in source/output files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
from roboflow_config import load_local_settings, model_id
MODEL_ID = "seat-analysis-8ssal/1"  # Trained model in user's own workspace
CHAIR_CLASSES = {"empty-chair", "occupied-chair-back", "occupied-chair-front", "occupied-chair-side"}
COLORS = {"AVAILABLE": (65, 185, 38), "OCCUPIED": (54, 54, 235), "OTHER": (230, 190, 75)}  # BGR


def require_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV missing. Run: python -m pip install opencv-python") from exc
    return cv2


def save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def get_samples(video_path: Path, every_s: float, max_samples: int):
    cv2 = require_cv2()
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    if fps <= 0:
        capture.release()
        raise RuntimeError("Video frame rate unavailable")
    duration = count / fps if count > 0 else 0.0
    sample_times = []
    t = 0.0
    while (not duration or t < duration) and len(sample_times) < max_samples:
        sample_times.append(round(t, 4))
        t += every_s
    samples = []
    try:
        for t in sample_times:
            capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = capture.read()
            if not ok:
                break
            # Actual decoded timestamp can differ slightly from seek target.
            actual_t = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            samples.append((round(actual_t, 3) if actual_t > 0 else t, frame))
    finally:
        capture.release()
    return {"fps": round(fps, 3), "duration_seconds": round(duration, 3), "width": int(samples[0][1].shape[1]) if samples else 0,
            "height": int(samples[0][1].shape[0]) if samples else 0}, samples


def state_of_class(label: str) -> str:
    name = label.lower().replace("_", "-").strip()
    if name == "empty-chair":
        return "AVAILABLE"
    if name.startswith("occupied-chair"):
        return "OCCUPIED"
    return "OTHER"


def parse_model_response(raw: object, width: int, height: int, threshold: float) -> list[dict]:
    if not isinstance(raw, dict):
        raise ValueError("Expected JSON dict from Roboflow")
    preds = raw.get("predictions", [])
    if isinstance(preds, dict):
        preds = preds.get("predictions", [])
    if not isinstance(preds, list):
        raise ValueError("Unexpected prediction payload")
    out = []
    for obj in preds:
        if not isinstance(obj, dict) or any(k not in obj for k in ("x", "y", "width", "height", "class")):
            continue
        conf = float(obj.get("confidence", 0))
        if conf < threshold:
            continue
        cls = str(obj["class"]).lower().replace("_", "-").strip()
        x, y, w, h = (float(obj[k]) for k in ("x", "y", "width", "height"))
        box = [max(0, int(round(x - w / 2))), max(0, int(round(y - h / 2))),
               min(width - 1, int(round(x + w / 2))), min(height - 1, int(round(y + h / 2)))]
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        out.append({"class": cls, "confidence": round(conf, 4), "state": state_of_class(cls), "bbox_xyxy": box})
    return out


def counts_for(detections: list[dict]) -> dict:
    return {
        "available_chair_detections": sum(p["state"] == "AVAILABLE" for p in detections),
        "occupied_chair_detections": sum(p["state"] == "OCCUPIED" for p in detections),
        "other_detections": sum(p["state"] == "OTHER" for p in detections),
    }


def draw_detections(frame, detections: list[dict], seconds: float):
    cv2 = require_cv2()
    out = frame.copy()
    h, w = out.shape[:2]
    for p in detections:
        color = COLORS[p["state"]]
        x1, y1, x2, y2 = p["bbox_xyxy"]
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f'{p["class"]} {round(100 * p["confidence"])}%'
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.47 if w < 1000 else 0.62
        (tw, th), _ = cv2.getTextSize(label, font, scale, 1)
        # Ensure the tag stays within the image when the box reaches an edge.
        tx, ty = max(0, min(x1, w - tw - 8)), max(th + 8, y1 - 3)
        cv2.rectangle(out, (tx, ty - th - 7), (tx + tw + 7, ty + 4), color, -1)
        cv2.putText(out, label, (tx + 3, ty - 1), font, scale, (255, 255, 255), 1, cv2.LINE_AA)
    overlay = out.copy()
    cv2.rectangle(overlay, (0, 0), (min(w - 1, 425), 42), (17, 32, 43), -1)
    cv2.addWeighted(overlay, .78, out, .22, 0, out)
    cv2.putText(out, f"RECORDED | sampled frame t={seconds:.1f}s", (8, 17),
                cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(out, "Boxes are real model predictions, NOT stable seat IDs", (8, 34),
                cv2.FONT_HERSHEY_SIMPLEX, .39, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def draft_photo_preview(photo: Path, map_path: Path, target: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    data = json.loads(map_path.read_text(encoding="utf-8"))
    image = Image.open(photo).convert("RGB")
    w, h = image.size
    if [w, h] != [data["reference_size"]["width"], data["reference_size"]["height"]]:
        raise ValueError("Photo dimensions differ from the draft mapping")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 23)
    except OSError:
        font = ImageFont.load_default()
    for seat in data["seats"]:
        x, y = int(seat["anchor"][0] * w), int(seat["anchor"][1] * h)
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill="#FFD166", outline="#1F2937", width=3)
        draw.rectangle((x + 15, y - 18, x + 90, y + 18), fill="#143D40")
        draw.text((x + 20, y - 12), seat["label"] + "?", fill="white", font=font)
    draw.rectangle((0, h - 34, min(w, 960), h), fill="#143D40")
    draw.text((10, h - 29), "PROVISIONAL PHOTO MAP | 8 candidate chairs | REVIEW IDs BEFORE USE", fill="white", font=font)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, quality=93)


def inspect(args):
    from PIL import Image, ImageDraw, ImageFont
    data, samples = get_samples(args.video, every_s=3.0, max_samples=6)
    if not samples:
        raise RuntimeError("No decodable video frames")
    args.output.mkdir(parents=True, exist_ok=True)
    # Contact sheet for review; no Roboflow predictions in inspect mode.
    cell_w, cell_h = 424, 218
    sheet = Image.new("RGB", (cell_w * 2, cell_h * 3), (242, 244, 246))
    canvas = ImageDraw.Draw(sheet)
    cv2 = require_cv2()
    for i, (time_s, frame) in enumerate(samples):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        small = Image.fromarray(rgb)
        small.thumbnail((424, 194))
        px, py = (i % 2) * cell_w, (i // 2) * cell_h
        canvas.text((px + 5, py + 3), f"Video at {time_s:.1f}s | no model run", fill=(25, 40, 50))
        sheet.paste(small, (px, py + 21))
    sheet.save(args.output / "video_sample_contact_sheet.jpg", quality=90)
    draft_photo_preview(args.photo, args.map, args.output / "draft_photo_seat_map.jpg")
    print(f"Video: {data['duration_seconds']}s, {data['width']}x{data['height']}, {data['fps']} fps")
    print("Image/photo map preview (NOT model predictions):", args.output / "draft_photo_seat_map.jpg")
    print("Video frame contact sheet (NOT model predictions):", args.output / "video_sample_contact_sheet.jpg")
    print("Camera motion is visible: don't reuse photo anchors across this recording.")


def get_client(api_key: str):
    try:
        from inference_sdk import InferenceHTTPClient, InferenceConfiguration
    except ImportError as exc:
        raise RuntimeError("Install SDK: python -m pip install inference-sdk") from exc
    client = InferenceHTTPClient(api_url="https://serverless.roboflow.com", api_key=api_key)
    return client.configure(InferenceConfiguration(api_key_transport="header"))


def infer(args):
    cv2 = require_cv2()
    data, samples = get_samples(args.video, args.interval, args.max_samples)
    if not samples:
        raise RuntimeError("No video samples read")
    key = os.environ.get("ROBOFLOW_API_KEY") or getpass.getpass("Roboflow API key (hidden): ")
    if not key:
        raise RuntimeError("Roboflow API key is required")
    client = get_client(key)
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for i, (t, frame) in enumerate(samples):
        with tempfile.TemporaryDirectory(prefix="sla_video_rf_") as d:
            image_file = Path(d) / "frame.jpg"
            if not cv2.imwrite(str(image_file), frame):
                raise RuntimeError("Could not create a temporary inference image")
            # Frame pixels are uploaded to the hosted Roboflow inference server.
            raw = client.infer(str(image_file), model_id=args.model_id)
        dets = parse_model_response(raw, frame.shape[1], frame.shape[0], args.threshold)
        counts = counts_for(dets)
        save_json(args.output / "raw_samples" / f"sample_{i:02d}.json", raw)
        annotated = draw_detections(frame, dets, t)
        frame_path = args.output / "annotated_frames" / f"sample_{i:02d}_{t:.1f}s.jpg"
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(frame_path), annotated)
        results.append({"sample_index": i, "video_time_seconds": t, "detections": dets, "counts": counts})
        print(f"t={t:.1f}s: available={counts['available_chair_detections']} occupied={counts['occupied_chair_detections']} other={counts['other_detections']}")
    report = {"schema_version": 1, "room_id": args.room_id, "model_id": args.model_id,
              "source": "recorded_video_roboflow_inference", "generated_at": datetime.now(timezone.utc).isoformat(),
              "input_video": args.video.name, "metadata": data, "sampling_interval_seconds": args.interval,
              "threshold": args.threshold,
              "seat_id_tracking": "NOT_CALIBRATED_CAMERA_MOVING" if args.camera_mode == "moving" else "FIXED_CAMERA_UNCALIBRATED",
              "camera_mode": args.camera_mode,
              "caution": "Counts are detections, not verified physical seats. No reservation/held-state predictions.",
              "samples": results}
    save_json(args.output / "video_detection_report.json", report)
    # This is deliberately a montage-style sampled video, not continuous footage
    # with boxes copied onto unanalysed moving frames (which would be misleading).
    first = cv2.imread(str(sorted((args.output / "annotated_frames").glob("sample_*.jpg"))[0]))
    h, w = first.shape[:2]
    clip = args.output / "sampled_detection_clip.mp4"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 2, (w, h))
    if not writer.isOpened():
        raise RuntimeError("Could not create annotated MP4; annotated JPG frames and JSON are saved")
    try:
        for img in sorted((args.output / "annotated_frames").glob("sample_*.jpg")):
            frame = cv2.imread(str(img))
            for _ in range(2):
                writer.write(frame)
    finally:
        writer.release()
    print("Saved:", clip)
    print("Saved:", args.output / "video_detection_report.json")
    print("Sampled clip shows actual model-detected frames, not continuous tracking.")


def main():
    load_local_settings()
    parser = argparse.ArgumentParser(description="SLA: inspect a room video or run Roboflow on sampled frames")
    parser.add_argument("mode", choices=["inspect", "infer"])
    parser.add_argument("--video", type=Path, default=HERE / "_outputs" / "source" / "hall_recorded_sample.mp4")
    parser.add_argument("--photo", type=Path, default=HERE / "_outputs" / "source" / "hall_reference_photo.jpg")
    parser.add_argument("--map", type=Path, default=HERE / "photo_seat_map_draft.json")
    parser.add_argument("--output", type=Path, default=HERE / "_outputs")
    parser.add_argument("--model-id", default=model_id(MODEL_ID))
    parser.add_argument("--room-id", default="demo-study-hall")
    parser.add_argument("--camera-mode", choices=["moving", "fixed"], default="moving",
                        help="Only specify fixed for a genuinely stationary camera")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between model samples, default 3")
    parser.add_argument("--max-samples", type=int, default=6, help="Cap Roboflow requests, default 6")
    parser.add_argument("--threshold", type=float, default=.5)
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error("Video not found: " + str(args.video))
    if args.mode == "inspect" and not args.photo.is_file():
        parser.error("Photo not found: " + str(args.photo))
    if args.interval <= 0 or args.max_samples < 1 or not 0 <= args.threshold <= 1:
        parser.error("--interval must be positive; --max-samples >= 1; threshold in [0,1]")
    if args.mode == "inspect":
        inspect(args)
    else:
        print(f"Sending up to {args.max_samples} sampled frames to Roboflow model {args.model_id}...")
        infer(args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        # Avoid logging SDK internals, query parameters or API key.
        print("Error:", str(exc).split("api_key=")[0][:220])
        raise SystemExit(1)
