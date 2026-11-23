"""First fixed-camera SLA experiment: image/video -> Roboflow detections -> seat JSON.

No API keys stored in the source. No backend writes in this first batch.
Run `python seat_pipeline.py --help` for examples.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLASSES = "empty-chair, occupied-chair-back, occupied-chair-front, occupied-chair-side, standing-person"


def load_map(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("seats") or not data.get("room_id"):
        raise ValueError("Seat map requires room_id and nonempty seats")
    ids = [s["seat_id"] for s in data["seats"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate seat IDs")
    for seat in data["seats"]:
        anchor = seat["anchor"]
        if len(anchor) != 2 or not all(0 <= float(v) <= 1 for v in anchor):
            raise ValueError(f"Invalid normalized anchor for {seat['seat_id']}")
    return data


def draw_preview(image_path: Path, seat_map: dict, output_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Install Pillow first: python -m pip install Pillow") from exc
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 23)
    except OSError:
        font = ImageFont.load_default()
    for seat in seat_map["seats"]:
        x, y = round(seat["anchor"][0] * w), round(seat["anchor"][1] * h)
        r = max(10, int(min(w, h) * .025))
        draw.ellipse((x-r,y-r,x+r,y+r), fill="#00B3B3", outline="white", width=4)
        name = seat.get("label", seat["seat_id"])
        try:
            bbox = draw.textbbox((0,0), name, font=font, stroke_width=2)
            tw = bbox[2]-bbox[0]
        except Exception:
            tw = 42
        bx, by = max(0, x-tw/2-8), min(h-35, y+r+5)
        draw.rounded_rectangle((bx,by,bx+tw+16,by+32),radius=5,fill="#093D48")
        draw.text((bx+8,by+2),name,font=font,fill="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)


def extract_predictions(response: Any) -> list[dict]:
    """Accept common Workflow/API response shapes without assuming a fixed output name."""
    collected: list[dict] = []
    def walk(v: Any, depth: int=0) -> None:
        if depth > 8:
            return
        if isinstance(v, dict):
            if "class" in v and any(k in v for k in ("x", "bbox", "box")):
                collected.append(v)
            else:
                for child in v.values():
                    walk(child, depth+1)
        elif isinstance(v, list):
            for child in v:
                walk(child, depth+1)
    walk(response)
    return collected


def bbox_center(pred: dict, w: int, h: int) -> tuple[float,float] | None:
    if all(k in pred for k in ("x","y")):
        x,y = float(pred["x"]),float(pred["y"])
        # Normalized or pixel-based Roboflow center coordinates.
        if x > 1 or y > 1:
            x /= w
            y /= h
        return x,y
    box = pred.get("bbox",pred.get("box"))
    if isinstance(box, dict):
        if all(k in box for k in ("x","y","width","height")):
            return bbox_center(box,w,h)
        if all(k in box for k in ("x1","x2","y1","y2")):
            return (float(box["x1"])+float(box["x2"]))/2/w,(float(box["y1"])+float(box["y2"]))/2/h
    if isinstance(box, (list, tuple)) and len(box)==4:
        x1,y1,x2,y2=map(float,box)
        return ((x1+x2)/2/w,(y1+y2)/2/h)
    return None


def classify(label: str) -> str | None:
    label = label.lower().strip().replace("_", "-")
    if label == "empty-chair":
        return "AVAILABLE"
    if label.startswith("occupied-chair"):
        return "OCCUPIED"
    # Standing persons, non-chair classes and belongings are not seat states.
    return None


def map_detections(seat_map: dict, response: Any, width: int, height: int,
                   max_distance: float=.15) -> dict:
    """A provisional nearest-chair matcher. Needs validation and calibration."""
    candidates = []
    for p in extract_predictions(response):
        state = classify(str(p.get("class", "")))
        pt = bbox_center(p, width, height)
        if state is None or pt is None:
            continue
        conf = float(p.get("confidence",p.get("confidence_score",0)))
        for i, seat in enumerate(seat_map["seats"]):
            ax,ay=seat["anchor"]
            # normalized x/y distances account approximately for aspect ratio
            distance=math.hypot((pt[0]-ax)*width/max(width,height), (pt[1]-ay)*height/max(width,height))
            if distance <= max_distance:
                candidates.append((distance, -conf, i, p, state, conf))
    # Greedy one-to-one assignment. Unmatched seats remain UNKNOWN.
    candidates.sort(key=lambda c:(c[0],c[1]))
    assigned_seats=set()
    assigned_predictions=set()
    assignments={}
    for dist,negconf,i,p,state,conf in candidates:
        key=id(p)
        if i in assigned_seats or key in assigned_predictions:
            continue
        assigned_seats.add(i)
        assigned_predictions.add(key)
        assignments[i]=(state,conf,p,dist)
    seats=[]
    for i, seat in enumerate(seat_map["seats"]):
        match=assignments.get(i)
        seats.append({
            "seat_id":seat["seat_id"],"label":seat.get("label",seat["seat_id"]),
            "physical_state":match[0] if match else "UNKNOWN",
            "confidence_score":round(match[1],4) if match else None,
            "anchor":seat["anchor"],
            "detected_class":str(match[2]["class"]) if match else None,
        })
    return {
        "room_id":seat_map["room_id"],"timestamp":datetime.now(timezone.utc).isoformat(),
        "source":"roboflow_workflow", "map_status":"provisional_unverified",
        "summary":{
            "total":len(seats),
            "available":sum(s["physical_state"]=="AVAILABLE" for s in seats),
            "occupied":sum(s["physical_state"]=="OCCUPIED" for s in seats),
            "unknown":sum(s["physical_state"]=="UNKNOWN" for s in seats),
        },
        "seats":seats,
    }


def infer_image(image_path: Path) -> Any:
    try:
        from inference_sdk import InferenceHTTPClient, InferenceConfiguration
    except ImportError as exc:
        raise RuntimeError("Install inference-sdk: python -m pip install inference-sdk") from exc
    key=os.environ.get("ROBOFLOW_API_KEY")
    workspace=os.environ.get("ROBOFLOW_WORKSPACE")
    workflow=os.environ.get("ROBOFLOW_WORKFLOW_ID")
    if not all((key,workspace,workflow)):
        raise RuntimeError("Set ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE and ROBOFLOW_WORKFLOW_ID in local environment variables (do NOT commit your API key).")
    client=InferenceHTTPClient(
        api_url="https://serverless.roboflow.com", api_key=key
    ).configure(InferenceConfiguration(api_key_transport="header"))
    return client.run_workflow(
        workspace_name=workspace, workflow_id=workflow,
        images={"image":str(image_path)},
        parameters={"classes":CLASSES}, use_cache=True
    )


def image_size(path: Path) -> tuple[int,int]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Install Pillow first: python -m pip install Pillow") from exc
    with Image.open(path) as image:
        return image.size


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2),encoding="utf-8")


def process_image(image_path: Path,seat_map: dict,output_dir: Path,
                  raw_response: Any=None) -> None:
    w,h=image_size(image_path)
    if raw_response is None:
        raw_response=infer_image(image_path)
    save_json(output_dir/"raw_roboflow_response.json",raw_response)
    result=map_detections(seat_map,raw_response,w,h)
    save_json(output_dir/"latest_occupancy.json",result)
    print("Seat results:", result["summary"])
    print("Output:",(output_dir/"latest_occupancy.json").resolve())
    if not extract_predictions(raw_response):
        print("WARNING: No predictions could be extracted. Inspect raw_roboflow_response.json to adjust the response parser.",file=sys.stderr)


def process_video(video_path: Path,seat_map: dict,output_dir: Path,interval_sec: float) -> None:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Install opencv-python: python -m pip install opencv-python") from exc
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps=cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        raise RuntimeError("Could not detect video frame rate")
    stride=max(1,round(fps*interval_sec))
    frames=[]
    index=0
    try:
        while True:
            ok,frame=cap.read()
            if not ok:break
            if index % stride == 0:
                with tempfile.TemporaryDirectory(prefix="sla_cv_") as tmp:
                    tmp_image=Path(tmp)/"frame.jpg"
                    if not cv2.imwrite(str(tmp_image),frame):
                        raise RuntimeError("Could not write temporary frame")
                    response=infer_image(tmp_image)
                h,w=frame.shape[:2]
                result=map_detections(seat_map,response,w,h)
                result["video_second"]=round(index/fps,3)
                result["source"]="roboflow_workflow_video"
                frames.append(result)
                print(f"{result['video_second']}s: {result['summary']}")
            index+=1
    finally:
        cap.release()
    save_json(output_dir/"video_occupancy_frames.json",frames)
    if frames:
        save_json(output_dir/"latest_occupancy.json",frames[-1])
    print("Processed",len(frames),"video frames. Output:",output_dir.resolve())


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=["preview","image","video","from-json"])
    parser.add_argument("--map",dest="map_path",type=Path,default=Path(__file__).with_name("seat_map.json"))
    parser.add_argument("--image",type=Path,help="Reference / inference image")
    parser.add_argument("--video",type=Path,help="Recorded video")
    parser.add_argument("--predictions",type=Path,help="Saved Roboflow Workflow response for offline debugging")
    parser.add_argument("--output",type=Path,default=Path(__file__).parent / "_outputs")
    parser.add_argument("--interval",type=float,default=2.0,help="Seconds between sampled frames for video")
    args=parser.parse_args()
    seat_map=load_map(args.map_path)
    if args.mode in ("preview","image","from-json") and not args.image:
        parser.error("--image is required for this mode")
    if args.mode == "video" and not args.video:
        parser.error("--video is required for video mode")
    if args.mode == "from-json" and not args.predictions:
        parser.error("--predictions is required for from-json mode")
    if args.mode == "preview":
        draw_preview(args.image,seat_map,args.output/"seat_map_preview.jpg")
        print("Preview:",(args.output/"seat_map_preview.jpg").resolve())
    elif args.mode == "image":
        process_image(args.image,seat_map,args.output)
    elif args.mode == "from-json":
        process_image(args.image,seat_map,args.output,json.loads(args.predictions.read_text(encoding="utf-8")))
    elif args.mode == "video":
        if args.interval <= 0:parser.error("--interval must be positive")
        process_video(args.video,seat_map,args.output,args.interval)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError,ValueError,OSError) as exc:
        print(f"Error: {exc}",file=sys.stderr)
        raise SystemExit(1)
