"""Offline bridge: REAL Roboflow video detections -> provisional seat IDs + JSON.

No Roboflow call, no backend writes, no secrets. Uses existing video_detection_report.json.

Example:
  python camera_cloud_capture/seat_monitor_v1/seat_status_export.py

CRITICAL: First-frame IDs are provisional. This moving-camera recording cannot
be published as live physical occupancy; monitor a fixed camera after review.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from math import hypot
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHAIR_STATES = {'AVAILABLE', 'OCCUPIED'}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def iou(a: list[int], b: list[int]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1-x0) * max(0, y1-y0)
    area_a = max(0, a[2]-a[0]) * max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0]) * max(0, b[3]-b[1])
    return inter / max(1, area_a+area_b-inter)


def clean_detections(raw: list[dict], overlap: float=.8, ambiguity_gap: float=.15) -> tuple[list[dict],int]:
    """Combine boxes for the same physical chair; conflicting close scores -> UNKNOWN.

    Common Roboflow edge case: same box is empty-chair 0.768 and
    occupied-chair 0.625. This must NOT count as two different seats.
    """
    candidates = [dict(p) for p in raw if p.get('state') in CHAIR_STATES]
    candidates.sort(key=lambda p: float(p.get('confidence', 0)), reverse=True)
    groups: list[list[dict]] = []
    for p in candidates:
        placed = False
        for group in groups:
            if iou(p['bbox_xyxy'], group[0]['bbox_xyxy']) >= overlap:
                group.append(p);placed=True;break
        if not placed:
            groups.append([p])
    results=[]
    ambiguous=0
    for group in groups:
        highest=group[0]
        conflicting=[p for p in group[1:] if p['state'] != highest['state']]
        if conflicting and abs(float(highest['confidence'])-float(conflicting[0]['confidence'])) < ambiguity_gap:
            highest['state']='UNKNOWN';highest['ambiguity']='conflicting_empty_and_occupied';ambiguous+=1
        results.append(highest)
    return results,ambiguous


def center(p: dict, width:int, height:int) -> tuple[float,float]:
    x1,y1,x2,y2=p['bbox_xyxy']
    return (x1+x2)/(2*width), (y1+y2)/(2*height)


def build_first_frame_map(report:dict, room_id:str) -> tuple[dict,list[dict]]:
    width=int(report['metadata']['width']); height=int(report['metadata']['height'])
    sample=report['samples'][0]
    detections,ambig=clean_detections(sample['detections'])
    detections.sort(key=lambda p:center(p,width,height))
    seats=[]
    for index, p in enumerate(detections,1):
        label=f'S{index:02d}'
        seats.append({'seat_id':f'{room_id}-{label}','label':label,
                      'anchor':[round(v,6) for v in center(p,width,height)],
                      'reference_bbox_xyxy':p['bbox_xyxy'],
                      'reference_class':p['class']})
    proposal={'schema_version':1,'room_id':room_id,'camera_id':'recorded-demo-01',
              'camera_mode':'moving','confirmed':False,'source':'first_video_frame_roboflow_detections',
              'reference_sample_index':0,'reference_size':{'width':width,'height':height},
              'notes':'These IDs are only valid for this one frame. Review the complete physical seat inventory. For sustained monitoring, mount a fixed camera and make a NEW confirmed map from that fixed view.',
              'seats':seats}
    return proposal,detections


def assign(seats:list[dict], detections:list[dict], width:int,height:int,max_distance:float=.11) -> list[dict]:
    """One-to-one matching, unmatched chairs UNKNOWN, no invented occupancy."""
    candidate_pairs=[]
    for si,s in enumerate(seats):
        for di,p in enumerate(detections):
            ax,ay=s['anchor'];px,py=center(p,width,height)
            d=hypot(ax-px,ay-py)
            if d<=max_distance:
                candidate_pairs.append((d,si,di))
    candidate_pairs.sort()
    matched_s={};used_d=set()
    for d,si,di in candidate_pairs:
        if si not in matched_s and di not in used_d:
            matched_s[si]=detections[di];used_d.add(di)
    out=[]
    for si,s in enumerate(seats):
        pred=matched_s.get(si)
        row={'seat_id':s['seat_id'], 'status': (pred['state'] if pred else 'UNKNOWN').lower(),
             'confidence':float(pred['confidence']) if pred and pred['state']!='UNKNOWN' else None}
        if pred:
            x1,y1,x2,y2=pred['bbox_xyxy']
            row['coordinates']={'x1':x1,'y1':y1,'x2':x2,'y2':y2}
        out.append(row)
    return out


def counts(seats:list[dict]) -> dict:
    return {'total':len(seats), 'available':sum(s['status']=='available' for s in seats),
            'occupied':sum(s['status']=='occupied' for s in seats),
            'unknown':sum(s['status']=='unknown' for s in seats)}


def analyze_report(report:dict) -> list[dict]:
    rows=[]
    for sample in report['samples']:
        cleaned,ambig=clean_detections(sample['detections'])
        rows.append({'video_time_seconds':sample['video_time_seconds'],
                     'raw_chair_detections':sum(d.get('state') in CHAIR_STATES for d in sample['detections']),
                     'distinct_candidate_chairs':len(cleaned),
                     'available_candidates':sum(d['state']=='AVAILABLE' for d in cleaned),
                     'occupied_candidates':sum(d['state']=='OCCUPIED' for d in cleaned),
                     'ambiguous_candidates':ambig,
                     'note':'Frame-local detections only; NOT physical occupancy of fixed seat IDs'})
    return rows


def make_photo_preview(video:Path,time_s:float, proposed:dict, detections:list[dict], output:Path):
    try:
        import cv2
    except ImportError:
        print('OpenCV not installed: skipping preview JPG');return
    capture=cv2.VideoCapture(str(video))
    if not capture.isOpened():
        print('Original video unavailable: skipping preview JPG');return
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC,float(time_s)*1000)
        ok,frame=capture.read()
    finally:
        capture.release()
    if not ok: return
    for seat,p in zip(proposed['seats'], detections):
        # `proposed['seats']` and `detections` are both sorted by center.
        state=p['state']
        col=(55,200,55) if state=='AVAILABLE' else ((55,55,230) if state=='OCCUPIED' else (0,215,255))
        x1,y1,x2,y2=p['bbox_xyxy'];cv2.rectangle(frame,(x1,y1),(x2,y2),col,2)
        label=f"{seat['label']} {state} {p['confidence']:.0%}"
        font=cv2.FONT_HERSHEY_SIMPLEX;scale=.43
        (tw,th),_=cv2.getTextSize(label,font,scale,1)
        tx=max(0,min(x1,frame.shape[1]-tw-8)); ty=max(th+5,min(y1-5,frame.shape[0]-3))
        cv2.rectangle(frame,(tx,ty-th-4),(tx+tw+6,ty+3),col,-1)
        cv2.putText(frame,label,(tx+3,ty),font,scale,(255,255,255),1,cv2.LINE_AA)
    cv2.rectangle(frame,(0,0),(min(520,frame.shape[1]-1),23),(18,26,34),-1)
    cv2.putText(frame,'FIRST FRAME ONLY | MODEL OUTPUT | IDS UNVERIFIED',(6,17),cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1,cv2.LINE_AA)
    output.parent.mkdir(parents=True,exist_ok=True)
    cv2.imwrite(str(output),frame)


def main() -> None:
    parser=argparse.ArgumentParser(description='Produce review-only seat JSON from real Roboflow video results')
    parser.add_argument('--report',type=Path,default=HERE/'_outputs'/'video_detection_report.json')
    parser.add_argument('--video',type=Path,default=HERE/'_outputs'/'source'/'hall_recorded_sample.mp4')
    parser.add_argument('--output',type=Path,default=HERE/'_outputs')
    parser.add_argument('--confirmed-fixed-map',type=Path,default=None,
                        help='Optional CONFIRMED map from the SAME stationary camera. Generates per-frame snapshots.')
    args=parser.parse_args()
    report=json.loads(args.report.read_text(encoding='utf-8'))
    if not report.get('samples'): raise ValueError('Report contains no model samples')
    room_id=report['room_id']
    proposed,detections=build_first_frame_map(report,room_id)
    save_json(args.output/'seat_map_first_video_frame_UNVERIFIED.json',proposed)
    width,height=int(report['metadata']['width']),int(report['metadata']['height'])
    rows=assign(proposed['seats'],detections,width,height)
    snapshot={'room_id':room_id,'camera_id':'recorded-demo-01',
              'observed_at':report.get('generated_at', datetime.now(timezone.utc).isoformat()),
              'frame_index':0,'counts':counts(rows),'seats':rows}
    # Snapshot payload matches the earlier FastAPI occupancy schema but is
    # intentionally wrapped so nobody accidentally POSTs it as verified live data.
    wrapper={'schema_version':1,'publishable':False,'reason':'VIDEO CAMERA MOVES AND SEAT IDS NOT VERIFIED',
             'source':'real_roboflow_first_video_frame','source_video_time_seconds':report['samples'][0]['video_time_seconds'],
             'warning':'Preview snapshot is NOT a live reading and NOT ready for MongoDB / RSVP',
             'snapshot':snapshot,
             'frontend_preview_seats':[{'seat_id':s['seat_id'],'computed_state':s['status'].upper(),'confidence_score':s['confidence']} for s in rows]}
    save_json(args.output/'seat_occupancy_FIRST_FRAME_REVIEW_ONLY.json',wrapper)
    summary={'schema_version':1,'source':'real_roboflow_results','camera_mode':'moving',
             'observations':analyze_report(report),
             'note':'Frames are not registered to a fixed camera; cannot reliably update stable physical seats across this video.'}
    save_json(args.output/'video_detection_quality_report.json',summary)
    make_photo_preview(args.video,report['samples'][0]['video_time_seconds'],proposed,detections,
                       args.output/'seat_ids_first_video_frame_REVIEW.jpg')
    if args.confirmed_fixed_map:
        confirmed=json.loads(args.confirmed_fixed_map.read_text(encoding='utf-8'))
        if report.get('camera_mode') != 'fixed' or confirmed.get('camera_mode') != 'fixed' or confirmed.get('confirmed') is not True:
            raise ValueError('Refusing multi-frame seat IDs: both video report and confirmed map must be from a fixed camera')
        if confirmed.get('room_id') != room_id:
            raise ValueError('Confirmed seat-map room_id does not match model report')
        if confirmed.get('reference_size') != {'width':width,'height':height}:
            raise ValueError('Map/reference image dimensions differ from video')
        if not confirmed.get('seats') or len({s['seat_id'] for s in confirmed['seats']}) != len(confirmed['seats']):
            raise ValueError('Confirmed map must have nonempty unique seat IDs')
        for seat in confirmed['seats']:
            a=seat.get('anchor')
            if not isinstance(a,list) or len(a)!=2 or not all(isinstance(v,(int,float)) and 0<=v<=1 for v in a):
                raise ValueError('Seat anchor must be two normalized coordinates')
        timeline=[]
        for sample in report['samples']:
            cleaned,_=clean_detections(sample['detections'])
            mapped=assign(confirmed['seats'],cleaned,width,height)
            timeline.append({'video_time_seconds':sample['video_time_seconds'],
                             'snapshot':{'room_id':room_id,'camera_id':confirmed.get('camera_id','stationary-camera-01'),
                                         'observed_at':report.get('generated_at'),
                                         'frame_index':sample['sample_index'],'counts':counts(mapped),'seats':mapped}})
        save_json(args.output/'fixed_camera_seat_timeline_REVIEW.json',
                  {'schema_version':1,'source':'recorded_fixed_camera','replay_only':True,
                   'booking_safe':False,'note':'Recorded playback is NOT live. Validate in your API before writing to production.',
                   'samples':timeline})
        print('Saved fixed-camera mapping timeline:',args.output/'fixed_camera_seat_timeline_REVIEW.json')
    print('Real Roboflow report parsed:', len(summary['observations']),'sampled frames')
    print('Initial unique chair candidates:',len(proposed['seats']))
    print('Provisional first-frame status:',snapshot['counts'])
    for row in summary['observations']:
        if row['ambiguous_candidates']:
            print(f"Ambiguous overlapping chair at t={row['video_time_seconds']}s; not counted as occupied.")
    print('Saved:',args.output/'seat_map_first_video_frame_UNVERIFIED.json')
    print('Saved:',args.output/'seat_occupancy_FIRST_FRAME_REVIEW_ONLY.json')
    print('Saved:',args.output/'video_detection_quality_report.json')
    print('No frontend/backend/MongoDB writes. Camera must be fixed and IDs reviewed first.')

if __name__=='__main__':
    main()
