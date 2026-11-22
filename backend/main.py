from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from createRandomData import generate_campus_occupancy_data
from database.db import db_instance, hash_password
from database.models import (
    ConfirmHandRequest,
    FriendRequestCreate,
    FriendRequestRespond,
    LoginRequest,
    ProfileUpdateRequest,
    RaiseHandRequest,
    RSVPCreateRequest,
    RSVPToggleRequest,
    SignupRequest,
)

app = FastAPI(title="StudySpot IITB API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def homepage():
    return {
        "message": "StudySpot IITB API is running",
        "mongodb_cloud_connected": db_instance.using_cloud,
    }


# ---------------- AUTH ----------------
@app.post("/api/auth/signup")
async def signup(payload: SignupRequest):
    existing = db_instance.get_user(payload.roll_number)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this university roll number already exists.",
        )

    user_doc = {
        "roll_number": payload.roll_number.strip().upper(),
        "full_name": payload.full_name.strip(),
        "email": payload.email.strip().lower(),
        "password_hash": hash_password(payload.password),
        "branch": payload.branch.strip() or "Computer Science",
        "hostel": payload.hostel.strip() or "Hostel 4",
        "bio": "Studying on campus via StudySpot.",
    }
    created = db_instance.create_user(user_doc)
    return {"user": created}


@app.post("/api/auth/login")
async def login(payload: LoginRequest):
    user = db_instance.get_user(payload.roll_number)
    if not user or user.get("password_hash") != hash_password(payload.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid roll number or password.",
        )
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"user": safe_user}


# ---------------- USERS & PROFILES ----------------
@app.get("/api/users/search")
async def search_users(
    q: str = Query(default=""),
    viewer_roll: str = Query(default=""),
):
    matched = db_instance.search_users(q)
    active_hands = {
        h["user_roll"].upper(): h for h in db_instance.get_active_hands()
    }
    results = []
    for u in matched:
        roll = u["roll_number"].upper()
        rel = (
            db_instance.get_relationship(viewer_roll, roll)["status"]
            if viewer_roll
            else "NONE"
        )
        # Only expose active study room if they are friends or self
        active_hand = (
            active_hands.get(roll) if rel in ("FRIENDS", "SELF") else None
        )
        results.append(
            {
                **u,
                "relationship": rel,
                "active_hand": active_hand,
            }
        )
    return {"users": results}


@app.get("/api/users/{roll_number}")
async def get_user_profile(
    roll_number: str,
    viewer_roll: str = Query(default=""),
):
    user = db_instance.get_user(roll_number)
    if not user:
        raise HTTPException(status_code=404, detail="Student not found.")

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    roll = safe_user["roll_number"].upper()
    rel = (
        db_instance.get_relationship(viewer_roll, roll)["status"]
        if viewer_roll
        else "NONE"
    )
    can_view_activity = rel in ("FRIENDS", "SELF")
    active_hand = db_instance.get_user_hand(roll) if can_view_activity else None

    all_rsvps = db_instance.get_rsvps()
    user_rsvps = (
        [
            r
            for r in all_rsvps
            if any(p["roll_number"].upper() == roll for p in r.get("participants", []))
        ]
        if can_view_activity
        else []
    )

    friendships = db_instance.get_all_friendships_for_user(roll)
    friends_count = sum(1 for f in friendships if f["status"] == "ACCEPTED")

    return {
        "profile": {
            **safe_user,
            "relationship": rel,
            "friends_count": friends_count,
            "active_hand": active_hand,
            "rsvps": user_rsvps,
        }
    }


@app.put("/api/users/{roll_number}")
async def update_user_profile(roll_number: str, payload: ProfileUpdateRequest):
    updated = db_instance.update_user(roll_number, payload.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found.")
    return {"user": updated}


# ---------------- FRIENDS ----------------
@app.get("/api/friends/{roll_number}")
async def get_friends_overview(roll_number: str):
    roll = roll_number.strip().upper()
    friendships = db_instance.get_all_friendships_for_user(roll)
    active_hands_map = {
        h["user_roll"].upper(): h for h in db_instance.get_active_hands()
    }

    friends = []
    incoming_requests = []
    outgoing_requests = []

    for f in friendships:
        s = f["sender_roll"].upper()
        r = f["receiver_roll"].upper()
        other_roll = r if s == roll else s
        other_user = db_instance.get_user(other_roll)
        if not other_user:
            continue
        safe_other = {k: v for k, v in other_user.items() if k != "password_hash"}

        if f["status"] == "ACCEPTED":
            friends.append(
                {
                    **safe_other,
                    "active_hand": active_hands_map.get(other_roll),
                }
            )
        elif r == roll:
            incoming_requests.append(
                {
                    **safe_other,
                    "requested_at": f.get("created_at"),
                }
            )
        else:
            outgoing_requests.append(
                {
                    **safe_other,
                    "requested_at": f.get("created_at"),
                }
            )

    studying_now = [fr for fr in friends if fr.get("active_hand") is not None]
    return {
        "friends": friends,
        "studying_now": studying_now,
        "incoming_requests": incoming_requests,
        "outgoing_requests": outgoing_requests,
    }


@app.post("/api/friends/request")
async def send_friend_request(payload: FriendRequestCreate):
    if payload.sender_roll.strip().upper() == payload.receiver_roll.strip().upper():
        raise HTTPException(status_code=400, detail="Cannot add yourself.")
    res = db_instance.send_friend_request(payload.sender_roll, payload.receiver_roll)
    return res


@app.post("/api/friends/respond")
async def respond_friend_request(payload: FriendRequestRespond):
    res = db_instance.respond_friend_request(
        payload.sender_roll, payload.receiver_roll, payload.action
    )
    return res


@app.delete("/api/friends/{user_a}/{user_b}")
async def remove_friend(user_a: str, user_b: str):
    db_instance.remove_friend(user_a, user_b)
    return {"status": "NONE"}


# ---------------- RAISE HAND (CHECK-IN WITH AUTO-EXPIRY) ----------------
@app.get("/api/hands")
async def list_active_hands():
    return {"active_hands": db_instance.get_active_hands()}


@app.post("/api/hands/raise")
async def raise_hand(payload: RaiseHandRequest):
    hand = db_instance.raise_hand(
        user_roll=payload.user_roll,
        zone_name=payload.zone_name,
        room_id=payload.room_id,
        room_name=payload.room_name,
        note=payload.note,
        duration_minutes=payload.duration_minutes,
    )
    return {"active_hand": hand}


@app.post("/api/hands/confirm")
async def confirm_still_studying(payload: ConfirmHandRequest):
    hand = db_instance.confirm_hand(
        user_roll=payload.user_roll,
        extend_minutes=payload.extend_minutes,
    )
    if not hand:
        raise HTTPException(status_code=404, detail="No active raised hand found.")
    return {"active_hand": hand}


@app.delete("/api/hands/{user_roll}")
async def lower_hand(user_roll: str):
    db_instance.lower_hand(user_roll)
    return {"active_hand": None}


# ---------------- RSVPS (POKEMON GO STYLE STUDY SESSIONS) ----------------
@app.get("/api/rsvps")
async def list_rsvps(zone_name: str | None = Query(default=None)):
    return {"rsvps": db_instance.get_rsvps(zone_name)}


@app.post("/api/rsvps")
async def create_rsvp(payload: RSVPCreateRequest):
    rsvp = db_instance.create_rsvp(
        creator_roll=payload.creator_roll,
        zone_name=payload.zone_name,
        room_id=payload.room_id,
        room_name=payload.room_name,
        start_time=payload.start_time,
        end_time=payload.end_time,
        topic=payload.topic,
    )
    return {"rsvp": rsvp}


@app.post("/api/rsvps/{rsvp_id}/toggle")
async def toggle_rsvp(rsvp_id: str, payload: RSVPToggleRequest):
    updated = db_instance.toggle_rsvp_participant(rsvp_id, payload.user_roll)
    if not updated:
        raise HTTPException(status_code=404, detail="RSVP session not found.")
    return {"rsvp": updated}


# ---------------- CCTV CAMPUS OCCUPANCY ----------------
@app.get("/api/occupancy")
async def get_occupancy():
    return db_instance.get_occupancy()


@app.post("/api/occupancy/refresh")
async def refresh_occupancy():
    data = generate_campus_occupancy_data()
    db_instance.save_occupancy(data)
    return data
