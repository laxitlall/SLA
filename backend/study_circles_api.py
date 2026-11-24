"""Study Circles: isolated MongoDB-backed demo room reservations.

Prototype limitations:
- Identity is asserted by the calling frontend; add authenticated sessions/RBAC
  before making this public.
- One demonstrator room (H15 Room 2), one-hour whole-hour slots.
- This does NOT reserve a real IIT Bombay room or change camera seat data.
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError, PyMongoError
except ImportError:  # prevents the rest of the application crashing on import
    MongoClient = None

    class DuplicateKeyError(Exception):
        pass

    class PyMongoError(Exception):
        pass


router = APIRouter(prefix="/api/study-circles", tags=["Study Circles"])
ROOT = Path(__file__).resolve().parent.parent
for env_path in (ROOT / ".env", ROOT / "backend" / ".env", ROOT / "backend" / "atlas-credentials.env"):
    load_dotenv(env_path, override=False)

ROOM = {"room_id": "h15-room-2", "zone_name": "Hostel 15", "room_name": "Study Room 2", "group_capacity": 6}
START_HOURS = range(9, 22)  # 09:00–10:00 through 21:00–22:00 local time
IST = timezone(timedelta(hours=5, minutes=30))
_client = None
_collection = None
_db_lock = threading.Lock()


def get_collection():
    """Connect lazily so the original CV server isn't affected by missing MongoDB."""
    global _client, _collection
    if _collection is not None:
        return _collection
    with _db_lock:
        if _collection is not None:
            return _collection
        if MongoClient is None:
            raise HTTPException(503, "Study Circles requires pymongo. Install backend requirements.")
        uri = (os.environ.get("STUDY_CIRCLES_MONGODB_URI")
               or os.environ.get("MONGODB_URI")
               or os.environ.get("MONGO_URI") or "").strip()
        if not uri:
            raise HTTPException(503, "MongoDB URI missing. Set MONGODB_URI in the project .env.")
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=4000)
            client.admin.command("ping")
            db_name = (os.environ.get("STUDY_CIRCLES_DB_NAME") or os.environ.get("MONGODB_DB_NAME") or os.environ.get("DB_NAME") or "studyspot").strip()
            col = client[db_name]["study_circle_bookings_v1"]
            # _id is a deterministic room/date/hour key; MongoDB already
            # enforces a unique index on _id, even for concurrent requests.
            col.create_index("booking_id", unique=True)
            col.create_index("organizer_roll")
            col.create_index("invitees.roll_number")
            _client, _collection = client, col
            return col
        except PyMongoError as exc:
            raise HTTPException(503, "Study Circles MongoDB connection unavailable.") from exc


def now_local():
    return datetime.now(IST)


def normalize_roll(raw):
    val = str(raw).strip().upper()
    if not val or len(val) > 40 or any(not (ch.isalnum() or ch in "_-" ) for ch in val):
        raise HTTPException(422, "Invalid student roll number.")
    return val


def check_date_and_slot(day, slot, require_future=False):
    try:
        selected_day = Date.fromisoformat(day)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "Date must be YYYY-MM-DD.") from exc
    if selected_day.isoformat() != day:
        raise HTTPException(422, "Date must be YYYY-MM-DD.")
    valid = [f"{h:02d}:00" for h in START_HOURS]
    if slot is not None and slot not in valid:
        raise HTTPException(422, "Choose a one-hour slot between 09:00 and 22:00 IST.")
    today = now_local().date()
    if selected_day < today or selected_day > today + timedelta(days=14):
        raise HTTPException(422, "Choose a date from today through the next 14 days (IST).")
    if require_future:
        start = datetime.fromisoformat(f"{day}T{slot}:00").replace(tzinfo=IST)
        if start <= now_local():
            raise HTTPException(422, "The selected time has already started.")
    return selected_day


def public_record(doc):
    if not doc:
        return None
    return {k: v for k, v in doc.items() if k != "_id"}


class CreateBooking(BaseModel):
    organizer_roll: str
    date: str
    slot: str
    topic: str = Field(min_length=3, max_length=100)
    invitees: list[str] = Field(default_factory=list, max_length=5)


class RespondBooking(BaseModel):
    user_roll: str
    decision: Literal["ACCEPTED", "DECLINED"]


class SendReminder(BaseModel):
    sender_roll: str
    message: str = Field(min_length=1, max_length=220)


@router.get("/config")
def booking_config():
    return {"room": ROOM, "slots": [f"{h:02d}:00" for h in START_HOURS], "timezone": "Asia/Kolkata", "max_days_ahead": 14}


@router.get("/slots")
def booking_slots(date: str):
    check_date_and_slot(date, None)
    try:
        col = get_collection()
        busy = list(col.find({"room_id": ROOM["room_id"], "date": date}, {"_id": 0, "slot": 1}))
        return {"date": date, "booked_slots": [item["slot"] for item in busy]}
    except PyMongoError as exc:
        raise HTTPException(503, "Unable to check availability right now.") from exc


@router.get("/bookings")
def my_bookings(user_roll: str = Query(...)):
    roll = normalize_roll(user_roll)
    try:
        col = get_collection()
        cursor = col.find({"$or": [{"organizer_roll": roll}, {"invitees.roll_number": roll}]}, {"_id": 0}).sort([("date", 1), ("slot", 1)])
        return {"bookings": list(cursor)}
    except PyMongoError as exc:
        raise HTTPException(503, "Unable to load bookings right now.") from exc


@router.post("/bookings", status_code=201)
def create_booking(payload: CreateBooking):
    roll = normalize_roll(payload.organizer_roll)
    check_date_and_slot(payload.date, payload.slot, require_future=True)
    topic = payload.topic.strip()
    if len(topic) < 3:
        raise HTTPException(422, "Enter a study topic of at least three characters.")
    invited = [normalize_roll(x) for x in payload.invitees]
    if len(set(invited)) != len(invited) or roll in invited:
        raise HTTPException(422, "Invite each friend once; do not invite yourself.")
    if len(invited) + 1 > ROOM["group_capacity"]:
        raise HTTPException(422, "Group exceeds this demo room's booking limit.")

    doc = {
        "_id": f"{ROOM['room_id']}:{payload.date}:{payload.slot}",
        "booking_id": f"circle-{uuid.uuid4().hex[:12]}",
        "room_id": ROOM["room_id"], "room_name": ROOM["room_name"], "zone_name": ROOM["zone_name"],
        "group_capacity": ROOM["group_capacity"],
        "date": payload.date, "slot": payload.slot,
        "end_slot": f"{int(payload.slot[:2]) + 1:02d}:00", "timezone": "Asia/Kolkata",
        "topic": topic, "organizer_roll": roll,
        "invitees": [{"roll_number": r, "status": "PENDING"} for r in invited],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        get_collection().insert_one(doc)  # UNIQUE _id: exactly one client wins
        return {"booking": public_record(doc)}
    except DuplicateKeyError as exc:
        raise HTTPException(409, "That room and time slot has already been booked. Pick another.") from exc
    except PyMongoError as exc:
        raise HTTPException(503, "Unable to save booking to MongoDB.") from exc


@router.post("/bookings/{booking_id}/respond")
def respond_to_invite(booking_id: str, payload: RespondBooking):
    roll = normalize_roll(payload.user_roll)
    try:
        col = get_collection()
        target = {"booking_id": booking_id, "invitees": {"$elemMatch": {"roll_number": roll, "status": "PENDING"}}}
        result = col.update_one(target, {"$set": {"invitees.$.status": payload.decision}})
        if not result.modified_count:
            raise HTTPException(409, "This invitation was already answered or is unavailable.")
        doc = col.find_one({"booking_id": booking_id}, {"_id": 0})
        return {"booking": doc}
    except PyMongoError as exc:
        raise HTTPException(503, "Unable to update invitation.") from exc


@router.post("/bookings/{booking_id}/remind")
def send_reminder(booking_id: str, payload: SendReminder):
    """Persist a short in-app message for the organizer's invited group members.

    Identity is still asserted by the client in this prototype; real deployment
    requires verifying the logged-in organizer on the server.
    """
    sender = normalize_roll(payload.sender_roll)
    message = payload.message.strip()
    if not message:
        raise HTTPException(422, "Please enter a reminder message.")
    try:
        col = get_collection()
        query = {"booking_id": booking_id, "organizer_roll": sender}
        doc = col.find_one(query, {"_id": 0})
        if not doc:
            raise HTTPException(403, "Only the booking organizer can send reminders.")
        recipients = [i["roll_number"] for i in doc.get("invitees", [])
                      if i.get("status") in ("PENDING", "ACCEPTED")]
        if not recipients:
            raise HTTPException(409, "No pending or confirmed invitees to notify.")
        reminder = {
            "reminder_id": f"msg-{uuid.uuid4().hex[:12]}",
            "sender_roll": sender,
            "recipient_rolls": recipients,
            "message": message,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        # Protect against excess messages, including simultaneous sends.
        result = col.update_one({**query, "reminders.9": {"$exists": False}},
                                {"$push": {"reminders": reminder}})
        if not result.modified_count:
            raise HTTPException(409, "Booking cancelled or maximum 10 in-app reminders reached.")
        return {"sent": True, "recipients": len(recipients), "reminder_id": reminder["reminder_id"]}
    except PyMongoError as exc:
        raise HTTPException(503, "Unable to send in-app reminder. Try again.") from exc


@router.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: str, user_roll: str = Query(...)):
    roll = normalize_roll(user_roll)
    try:
        result = get_collection().delete_one({"booking_id": booking_id, "organizer_roll": roll})
        if not result.deleted_count:
            raise HTTPException(403, "Only the organizer can cancel an existing booking.")
        return {"cancelled": True}
    except PyMongoError as exc:
        raise HTTPException(503, "Unable to cancel booking.") from exc
