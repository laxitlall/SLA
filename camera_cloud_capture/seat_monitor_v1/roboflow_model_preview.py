"""SLA step 2: run *your trained Roboflow model* and draw actual detections.

Makes one hosted inference request on a reference photo. Does not update the
seat map, database, frontend, or any tracked application code.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
from roboflow_config import load_local_settings, model_id
MODEL_ID_FROM_SCREENSHOT = "seat-analysis-8ssal/1"  # Verify in Roboflow Deploy > API docs.
CHAIR_CLASSES = {
    "empty-chair", "occupied-chair-back", "occupied-chair-front", "occupied-chair-side"
}


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def parse_detections(raw: dict, min_confidence: float, image_w: int, image_h: int) -> list[dict]:
    preds = raw.get("predictions", [])
    if isinstance(preds, dict):
        preds = preds.get("predictions", [])
    if not isinstance(preds, list):
        raise ValueError("Unexpected Roboflow predictions format. See the saved raw response.")
    parsed = []
    for p in preds:
        if not isinstance(p, dict) or not all(k in p for k in ("x", "y", "width", "height", "class")):
            continue
        conf = float(p.get("confidence", 0))
        if conf < min_confidence:
            continue
        x, y = float(p["x"]), float(p["y"])
        w, h = float(p["width"]), float(p["height"])
        box = [max(0, round(x-w/2)), max(0, round(y-h/2)),
               min(image_w-1, round(x+w/2)), min(image_h-1, round(y+h/2))]
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        parsed.append({"class": str(p["class"]), "confidence": conf,
                       "x": x, "y": y, "width": w, "height": h, "box": box,
                       "is_chair": str(p["class"]).lower().replace("_", "-") in CHAIR_CLASSES})
    return parsed


def make_preview(image_path: Path, parsed: list[dict], output_dir: Path,
                 model_id: str, *, room_id: str) -> tuple[Path, Path, Path]:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("arial.ttf", max(15, width // 80))
    except OSError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", max(15, width // 80))
        except OSError:
            font = ImageFont.load_default()

    line_width = max(3, width // 500)
    for p in parsed:
        label = p["class"].lower().replace("_", "-")
        color = "#12B981" if label == "empty-chair" else ("#F43F5E" if label.startswith("occupied-chair") else "#38BDF8")
        x1, y1, x2, y2 = p["box"]
        draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)
        text = f"{p['class']} {p['confidence']:.0%}"
        text_box = draw.textbbox((0, 0), text, font=font)
        tw, th = text_box[2]-text_box[0], text_box[3]-text_box[1]
        ty = y1-th-10 if y1 >= th+10 else y1+4
        tx = min(x1, max(0,width-tw-12))
        draw.rectangle((tx,ty,tx+tw+10,ty+th+8), fill=color)
        draw.text((tx+5,ty+2), text, font=font, fill="#082F2B" if label == "empty-chair" else "#FFFFFF")

    output_dir.mkdir(parents=True, exist_ok=True)
    detections_path = output_dir / "roboflow_detection_preview.jpg"
    overlay.save(detections_path, quality=94)

    # Propose seat IDs *once* from the reference image. These are NOT final
    # calibration coordinates or a reliable per-frame tracking algorithm.
    chairs = [p for p in parsed if p["is_chair"]]
    chairs.sort(key=lambda p: (p["x"],p["y"]))
    proposal = image.copy()
    prop_draw = ImageDraw.Draw(proposal)
    seats = []
    for i, p in enumerate(chairs, 1):
        label = f"S{i:02d}"
        cx,cy = p["x"],p["y"]
        anchor = [round(cx/width,5), round(cy/height,5)]
        seats.append({"seat_id":f"{room_id}-{label}","label":label,
                      "anchor":anchor,"reference_class":p["class"],
                      "reference_confidence":round(p["confidence"],4),
                      "bbox_xyxy":p["box"]})
        x1, y1, x2, y2 = p["box"]
        prop_draw.rectangle((x1,y1,x2,y2), outline="#00D1C1", width=line_width)
        label_text = f"{label}?"
        prop_draw.rectangle((x1,max(0,y1-30),x1+65,max(25,y1-2)), fill="#064E3B")
        prop_draw.text((x1+5,max(0,y1-29)),label_text,font=font,fill="white")
    proposal_path = output_dir / "proposed_seat_map_preview.jpg"
    proposal.save(proposal_path, quality=94)

    proposal_json_path = output_dir / "proposed_seat_map.json"
    write_json(proposal_json_path, {
        "schema_version":1,
        "room_id":room_id,
        "reference_image":image_path.name,
        "reference_size":{"width":width,"height":height},
        "auto_generated_review_required":True,
        "note":"Draft only. Confirm that every physical chair has exactly one box and seat ID. Do not use these anchors across frames before checking video alignment.",
        "model_id":model_id,
        "seats":seats,
    })
    return detections_path, proposal_path, proposal_json_path


def main() -> None:
    load_local_settings()
    parser = argparse.ArgumentParser(description="Visualize real Roboflow model predictions")
    parser.add_argument("--image", type=Path, default=HERE / "room.jpeg")
    parser.add_argument("--model-id", default=model_id(MODEL_ID_FROM_SCREENSHOT))
    parser.add_argument("--room-id", default="demo-study-hall")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=HERE / "_outputs")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"Image not found: {args.image}")
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")

    try:
        from inference_sdk import InferenceHTTPClient, InferenceConfiguration
        from PIL import Image
    except ImportError as exc:
        parser.error(f"Missing package: {exc}. Install: python -m pip install inference-sdk Pillow")
    api_key = os.environ.get("ROBOFLOW_API_KEY") or getpass.getpass("Roboflow API key (input hidden; do not share): ")
    if not api_key:
        parser.error("No API key supplied")
    client = InferenceHTTPClient(api_url="https://serverless.roboflow.com", api_key=api_key).configure(
        InferenceConfiguration(api_key_transport="header")
    )
    print(f"Requesting your Roboflow model: {args.model_id}")
    raw = client.infer(str(args.image), model_id=args.model_id)
    if not isinstance(raw, dict):
        raise RuntimeError(f"Unexpected inference response type: {type(raw).__name__}")

    output_dir = args.output
    write_json(output_dir / "raw_roboflow_model_response.json", raw)
    with Image.open(args.image) as image:
        w,h = image.size
    detected = parse_detections(raw,args.threshold,w,h)
    paths = make_preview(args.image, detected, output_dir, args.model_id, room_id=args.room_id)
    print(f"Objects (confidence >= {args.threshold:.0%}): {len(detected)}")
    print(f"Detected chair candidates: {sum(p['is_chair'] for p in detected)}")
    print("Roboflow detection boxes:", paths[0].resolve())
    print("Proposed stable seat IDs:", paths[1].resolve())
    print("Proposed map JSON:", paths[2].resolve())
    print("Raw inference JSON:", (output_dir / "raw_roboflow_model_response.json").resolve())
    print("IMPORTANT: Review and correct provisional seat IDs before video monitoring.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not print API keys or full API request headers in debugging output.
        print("Inference failed:", str(exc).split("api_key=")[0][:300])
        raise SystemExit(1)
