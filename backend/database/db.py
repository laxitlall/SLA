import hashlib
import json
import os
import re
import uuid
from typing import Any, Iterable

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError 


logger = logging.getLogger("studyspot.db")


load_dotenv(os.path.join(Path(__file__).resolve().parent.parent,"atlas-credentials.env"))
load_dotenv(os.path.join(Path(__file__).resolve().parent.parent,".env"))

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "sl_db").strip()

BASE_DIR = Path(__file__).resolve().parent
# OCCUPANCY_FILE = BASE_DIR / "campus_occupancy.json"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(iso_str: str) -> datetime:
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1] + "+00:00"
    return datetime.fromisoformat(iso_str)

OCCUPANCY_DOC_ID = "campus_live"

# Fields that exist only for authentication/security and are never returned to clients.
INTERNAL_USER_FIELDS = (
    "password_hash",
    "token_version",
    "failed_login_count",
    "locked_until",
    "last_login_at",
    "created_at",
)
EDITABLE_PROFILE_FIELDS = ("full_name", "branch", "hostel", "bio")


def _exclude(*fields: str) -> dict[str, int]:
    return {"_id": 0, **{field: 0 for field in fields}}


SELF_PROJECTION = _exclude(*INTERNAL_USER_FIELDS)
# What other students may see: no e-mail address, no role.
OTHER_PROJECTION = _exclude(*INTERNAL_USER_FIELDS, "email", "role")


def strip_internal(user: dict) -> dict:
    """Remove security-internal fields from a full user document."""
    
    clean = {k: v for k, v in user.items() if k not in INTERNAL_USER_FIELDS and k != "_id"}
    clean.setdefault("role", "student")
    return clean



# DEFAULT_USERS = [
#     {
#         "roll_number": "26M0821",
#         "full_name": "Laxit Lall",
#         "email": "26m0821@iitb.ac.in",
#         "password_hash": hash_password("password123"),
#         "branch": "Computer Science",
#         "hostel": "Hostel 15",
#         "bio": "Ghare jaake sutti babu",
#     },
#     {
#         "roll_number": "26M0829",
#         "full_name": "Ayush Raj",
#         "email": "26m0829@iitb.ac.in",
#         "password_hash": hash_password("password123"),
#         "branch": "Computer Science",
#         "hostel": "Hostel 15",
#         "bio": "Ghare jaake sutti babu",
#     },
#     {
#         "roll_number": "26M0828",
#         "full_name": "sushil kumar",
#         "email": "26m0828@iitb.ac.in",
#         "password_hash": hash_password("password123"),
#         "branch": "Computer Science",
#         "hostel": "Hostel 10",
#         "bio": "Ghare jaake sutti babu",
#     },
# ]


class StudySpotDatabase:
    """
    MongoDB Atlas Cloud database wrapper.
    Connects to MongoDB Atlas when MONGODB_URI is provided in backend/.env.
    Falls back seamlessly to an in-memory/JSON store if MONGODB_URI is not configured yet.
    """
    # -----------Setup and Intialization----------#
    def __init__(self):
        self.mongo_client = AsyncMongoClient | None = None
        self.db = None
        self.using_cloud = False
        self._connect()

    async def _connect(self) -> None:
        self.client = AsyncMongoClient(
            host=MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            tz_aware=True
        )
        await self.client.admin.command("ping") 
        self.db = self.client[DB_NAME]
        await self._ensure_indexes()
        logger.info("Connected to MongoDB database %r", DB_NAME)

    
    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
        self.client = None
        self.db = None

    
    async def ping(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:  # noqa: BLE001 - any failure (incl. not connected) means "down"
            return False


    async def _ensure_indexes(self) -> None:
        db = self.db
        await db.users.create_index("roll_number", unique=True)
        await db.users.create_index("email", unique=True)
        await db.friendships.create_index(
            [("sender_roll", 1), ("receiver_roll", 1)], unique=True
        )
        await db.friendships.create_index("receiver_roll")
        await db.active_hands.create_index("user_roll", unique=True)
        # TTL index: MongoDB removes a raised hand shortly after expires_at_dt passes.
        await db.active_hands.create_index("expires_at_dt", expireAfterSeconds=0)
        await db.rsvps.create_index("rsvp_id", unique=True)
        await db.rsvps.create_index("participants.roll_number")
        await db.refresh_tokens.create_index("jti", unique=True)
        await db.refresh_tokens.create_index("family_id")
        await db.refresh_tokens.create_index("user_roll")
        await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
        await db.libraries.create_index("library_id", unique=True)
        await db.cameras.create_index("camera_id", unique=True)

    #--------------- Setup ends --------------#
        

    # ---------------- USERS ----------------
    # TODO tell laxit to change requests
    async def get_user(self, roll_number: str,include_private: bool = True) -> dict | None:
        # roll = roll_number.strip().upper()
        projection = SELF_PROJECTION if include_private else OTHER_PROJECTION
        doc = await self.db.users.find_one({"roll_number": roll_number.strip().upper()}, projection)
        if doc and include_private:
            doc.setdefault("role", "student")
        return doc
    

    async def create_user(self, user_doc: dict) -> dict:
        doc = {
            "role": "student",
            "token_version": 0,
            "failed_login_count": 0,
            "locked_until": None,
            "created_at": utc_now(),
            **user_doc,
        }
        doc["roll_number"] = doc["roll_number"].strip().upper()
        doc["email"] = doc["email"].strip().lower()
        await self.db.users.insert_one(dict(doc))
        return strip_internal(doc)

    async def update_user(self, roll_number: str, updates: dict) -> dict | None:
        roll = roll_number.strip().upper()
        clean = {k: v for k, v in updates.items() if k in EDITABLE_PROFILE_FIELDS and v is not None}
        if clean:
            result = await self.db.users.update_one({"roll_number": roll}, {"$set": clean})
            if result.matched_count == 0:
                return None
        return await self.get_user(roll)

    async def search_users(self, query: str,limit: int = 50) -> list[dict]:
        q = query.strip()
        flt: dict[str, Any] = {}
        if q:
            pattern = re.escape(q)  # user input is matched literally, never as a regex
            flt = {
                "$or": [
                    {field: {"$regex": pattern, "$options": "i"}}
                    for field in ("roll_number", "full_name", "branch", "hostel")
                ]
            }
        cursor = self.db.users.find(flt, OTHER_PROJECTION).sort("roll_number", 1).limit(limit)
        return await cursor.to_list(length=limit)

    #-------------------User Ends----------------#


    # ---------------- FRIENDSHIPS ----------------
    async def get_all_friendships_for_user(self, roll_number: str) -> list[dict]:
        roll = roll_number.strip().upper()
        cursor = self.db.friendships.find(
            {"$or": [{"sender_roll": roll}, {"receiver_roll": roll}]}, {"_id": 0}
        )
        return await cursor.to_list(length=None)



    async def get_relationship(self, user_a: str, user_b: str) -> dict:
        a, b = user_a.strip().upper(), user_b.strip().upper()
        if a == b:
            return {"status": "SELF"}
        f = await self.db.friendships.find_one(
            {
                "$or": [
                    {"sender_roll": a, "receiver_roll": b},
                    {"sender_roll": b, "receiver_roll": a},
                ]
            },
            {"_id": 0},
        )
        if not f:
            return {"status": "NONE"}
        if f["status"] == "ACCEPTED":
            return {"status": "FRIENDS"}
        if f["sender_roll"].upper() == a:
            return {"status": "OUTGOING_PENDING"}
        return {"status": "INCOMING_PENDING"}

    async def send_friend_request(self, sender_roll: str, receiver_roll: str) -> dict:
        s, r = sender_roll.strip().upper(), receiver_roll.strip().upper()
        rel = (await self.get_relationship(s, r))["status"]
        if rel in ("FRIENDS", "OUTGOING_PENDING"):
            return {"status": rel}
        if rel == "INCOMING_PENDING":  # they already asked us: sending one back accepts it
            return await self.respond_friend_request(r, s, "ACCEPT") or {"status": "NONE"}
        try:
            await self.db.friendships.insert_one(
                {
                    "sender_roll": s,
                    "receiver_roll": r,
                    "status": "PENDING",
                    "created_at": iso_z(utc_now()),
                }
            )
        except DuplicateKeyError:  # double-click / concurrent request
            pass
        return {"status": "OUTGOING_PENDING"}

    async def respond_friend_request(self, sender_roll: str, receiver_roll: str, action: str) -> dict:
        s, r = sender_roll.strip().upper(), receiver_roll.strip().upper()
        pending = {"sender_roll": s, "receiver_roll": r, "status": "PENDING"}
        if action.strip().upper() == "ACCEPT":
            result = await self.db.friendships.update_one(
                pending, {"$set": {"status": "ACCEPTED", "accepted_at": iso_z(utc_now())}}
            )
            return {"status": "FRIENDS"} if result.matched_count else None
        result = await self.db.friendships.delete_one(pending)
        return {"status": "NONE"} if result.deleted_count else None

    async def remove_friend(self, user_a: str, user_b: str) -> None:
        a, b = user_a.strip().upper(), user_b.strip().upper()
        await self.db.friendships.delete_many(
            {
                "$or": [
                    {"sender_roll": a, "receiver_roll": b},
                    {"sender_roll": b, "receiver_roll": a},
                ]
            }
        )

    # ---------------- RAISE HAND (ACTIVE CHECK-INS) ----------------
    async def _enrich_hands(self, hands: list[dict]) -> list[dict]:
        now = utc_now()
        users = await self.get_users_by_rolls([h["user_roll"] for h in hands])
        enriched = []
        for h in hands:
            user = users.get(h["user_roll"].upper())
            expires = h.pop("expires_at_dt", None) or parse_iso(h["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            remaining = max(0, int((expires - now).total_seconds() // 60))
            enriched.append(
                {
                    **h,
                    "full_name": user["full_name"] if user else h["user_roll"],
                    "branch": user.get("branch", "") if user else "",
                    "hostel": user.get("hostel", "") if user else "",
                    "remaining_minutes": remaining,
                    "needs_confirmation": remaining <= 15,
                }
            )
        return enriched

    async def get_active_hands(self, rolls: Iterable[str] | None = None) -> list[dict]:
        """Active hands, optionally restricted to the given roll numbers."""
        flt: dict[str, Any] = {"expires_at_dt": {"$gt": utc_now()}}
        if rolls is not None:
            wanted = list({r.strip().upper() for r in rolls})
            if not wanted:
                return []
            flt["user_roll"] = {"$in": wanted}
        cursor = self.db.active_hands.find(flt, {"_id": 0})
        return await self._enrich_hands(await cursor.to_list(length=None))



    async def get_user_hand(self, user_roll: str) -> dict | None:
        hands = await self.get_active_hands([user_roll])
        return hands[0] if hands else None

    async def raise_hand(
        self,
        user_roll: str,
        zone_name: str,
        room_id: str,
        room_name: str,
        note: str = "Studying",
        duration_minutes: int = 120,
    ) -> dict:
        roll = user_roll.strip().upper()
        now = utc_now()
        expires = now + timedelta(minutes=duration_minutes)
        await self.db.active_hands.replace_one(
            {"user_roll": roll},
            {
                "user_roll": roll,
                "zone_name": zone_name,
                "room_id": room_id,
                "room_name": room_name,
                "note": note,
                "raised_at": iso_z(now),
                "expires_at": iso_z(expires),
                "expires_at_dt": expires,
            },
            upsert=True,
        )
        return await self.get_user_hand(roll)
    

    async def confirm_hand(self, user_roll: str, extend_minutes: int = 60) -> dict | None:
        roll = user_roll.strip().upper()
        now = utc_now()
        new_expires = now + timedelta(minutes=extend_minutes)
        result = await self.db.active_hands.update_one(
            {"user_roll": roll, "expires_at_dt": {"$gt": now}},
            {"$set": {"expires_at": iso_z(new_expires), "expires_at_dt": new_expires}},
        )
        if result.matched_count == 0:
            return None
        return await self.get_user_hand(roll)

    async def lower_hand(self, user_roll: str):
        # roll = user_roll.strip().upper()
        await self.db.active_hands.delete_one({"user_roll": user_roll.strip().upper()})

    # ---------------- RSVPS (POKEMON GO STYLE LOBBIES) ----------------
    async def get_rsvps(
        self, zone_name: str | None = None, 
        participant_roll: str | None = None, 
        limit: int = 200
    ) -> list[dict]:
        flt: dict[str, Any] = {}
        if zone_name:
            flt["zone_name"] = zone_name
        if participant_roll:
            flt["participants.roll_number"] = participant_roll.strip().upper()
        cursor = self.db.rsvps.find(flt, {"_id": 0}).sort("_id", -1).limit(limit)  # newest first
        return await cursor.to_list(length=limit)


    async def create_rsvp(
        self,
        creator_roll: str,
        zone_name: str,
        room_id: str,
        room_name: str,
        start_time: str,
        end_time: str,
        topic: str,
    ) -> dict:
        roll = creator_roll.strip().upper()
        user = self.get_user(roll)
        creator_name = user["full_name"] if user else roll
        rsvp_doc = {
            "rsvp_id": f"rsvp-{uuid.uuid4().hex[:8]}",
            "creator_roll": roll,
            "creator_name": creator_name,
            "zone_name": zone_name,
            "room_id": room_id,
            "room_name": room_name,
            "start_time": start_time,
            "end_time": end_time,
            "topic": topic,
            "participants": [{"roll_number": roll, "full_name": creator_name}],
        }
        if self.using_cloud:
            self.db.rsvps.insert_one(dict(rsvp_doc))
        else:
            data = self._read_local()
            data["rsvps"].insert(0, rsvp_doc)
            self._write_local(data)
        return rsvp_doc

    async def toggle_rsvp_participant(self, rsvp_id: str, user_roll: str) -> dict | None:
        roll = user_roll.strip().upper()
        user = self.get_user(roll)
        full_name = user["full_name"] if user else roll

        rsvps = self.get_rsvps()
        target = next((r for r in rsvps if r["rsvp_id"] == rsvp_id), None)
        if not target:
            return None

        participants = target.get("participants", [])
        exists = any(p["roll_number"].upper() == roll for p in participants)
        if exists:
            participants = [
                p for p in participants if p["roll_number"].upper() != roll
            ]
        else:
            participants.append({"roll_number": roll, "full_name": full_name})

        if self.using_cloud:
            if not participants:
                self.db.rsvps.delete_one({"rsvp_id": rsvp_id})
                return {"rsvp_id": rsvp_id, "deleted": True, "participants": []}
            self.db.rsvps.update_one(
                {"rsvp_id": rsvp_id}, {"$set": {"participants": participants}}
            )
        else:
            data = self._read_local()
            if not participants:
                data["rsvps"] = [
                    r for r in data["rsvps"] if r["rsvp_id"] != rsvp_id
                ]
                self._write_local(data)
                return {"rsvp_id": rsvp_id, "deleted": True, "participants": []}
            for r in data["rsvps"]:
                if r["rsvp_id"] == rsvp_id:
                    r["participants"] = participants
            self._write_local(data)

        target["participants"] = participants
        return target

    # ---------------- CCTV CAMPUS OCCUPANCY ----------------
    async def get_occupancy(self) -> dict:
        if self.using_cloud:
            doc = self.db.occupancy.find_one({"_id": "campus_live"}, {"_id": 0})
            if doc:
                return doc
        if OCCUPANCY_FILE.exists():
            with open(OCCUPANCY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"timestamp": iso_z(utc_now()), "zones": []}

    async def save_occupancy(self, campus_data: dict):
        with open(OCCUPANCY_FILE, "w", encoding="utf-8") as f:
            json.dump(campus_data, f, indent=4)
        if self.using_cloud:
            doc = {**campus_data, "_id": "campus_live"}
            self.db.occupancy.replace_one({"_id": "campus_live"}, doc, upsert=True)

    async def update_room_seats(
        self, zone_name: str, room_id: str, seats: list[dict]
    ) -> dict:
        campus_data = self.get_occupancy()
        campus_data["timestamp"] = iso_z(utc_now())
        for zone in campus_data.get("zones", []):
            if zone["name"].lower() == zone_name.strip().lower():
                for room in zone.get("rooms", []):
                    if room["room_id"].lower() == room_id.strip().lower():
                        room["seats"] = seats
                        break
        self.save_occupancy(campus_data)
        return campus_data


db_instance = StudySpotDatabase()
