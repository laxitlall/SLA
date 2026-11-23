import hashlib
import json
import os
import uuid

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

from pymongo import AsyncMongoClient, ReturnDocument

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
        self.mongo_client = AsyncMongoClient | None
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
    def get_user(self, roll_number: str) -> dict | None:
        roll = roll_number.strip().upper()
        if self.using_cloud:
            doc = self.db.users.find_one(
                {"roll_number": {"$regex": f"^{roll}$", "$options": "i"}}, {"_id": 0}
            )
            return doc
        data = self._read_local()
        for u in data["users"]:
            if u["roll_number"].upper() == roll:
                return dict(u)
        return None

    def create_user(self, user_doc: dict) -> dict:
        user_doc["roll_number"] = user_doc["roll_number"].strip().upper()
        if self.using_cloud:
            self.db.users.insert_one(dict(user_doc))
        else:
            data = self._read_local()
            data["users"].append(dict(user_doc))
            self._write_local(data)
        result = dict(user_doc)
        result.pop("password_hash", None)
        result.pop("_id", None)
        return result

    def update_user(self, roll_number: str, updates: dict) -> dict | None:
        roll = roll_number.strip().upper()
        clean_updates = {k: v for k, v in updates.items() if v is not None}
        if self.using_cloud:
            self.db.users.update_one(
                {"roll_number": {"$regex": f"^{roll}$", "$options": "i"}},
                {"$set": clean_updates},
            )
        else:
            data = self._read_local()
            for u in data["users"]:
                if u["roll_number"].upper() == roll:
                    u.update(clean_updates)
                    break
            self._write_local(data)
        user = self.get_user(roll)
        if user:
            user.pop("password_hash", None)
        return user

    def search_users(self, query: str) -> list[dict]:
        q = query.strip().lower()
        if self.using_cloud:
            if not q:
                cursor = self.db.users.find({}, {"_id": 0, "password_hash": 0})
            else:
                cursor = self.db.users.find(
                    {
                        "$or": [
                            {"roll_number": {"$regex": q, "$options": "i"}},
                            {"full_name": {"$regex": q, "$options": "i"}},
                            {"branch": {"$regex": q, "$options": "i"}},
                            {"hostel": {"$regex": q, "$options": "i"}},
                        ]
                    },
                    {"_id": 0, "password_hash": 0},
                )
            return list(cursor)

        data = self._read_local()
        results = []
        for u in data["users"]:
            if (
                not q
                or q in u["roll_number"].lower()
                or q in u["full_name"].lower()
                or q in u.get("branch", "").lower()
                or q in u.get("hostel", "").lower()
            ):
                copy_u = dict(u)
                copy_u.pop("password_hash", None)
                results.append(copy_u)
        return results

    #-------------------User Ends----------------#
    # ---------------- FRIENDSHIPS ----------------
    def get_all_friendships_for_user(self, roll_number: str) -> list[dict]:
        roll = roll_number.strip().upper()
        if self.using_cloud:
            cursor = self.db.friendships.find(
                {"$or": [{"sender_roll": roll}, {"receiver_roll": roll}]},
                {"_id": 0},
            )
            return list(cursor)
        data = self._read_local()
        return [
            f
            for f in data["friendships"]
            if f["sender_roll"].upper() == roll or f["receiver_roll"].upper() == roll
        ]

    def get_relationship(self, user_a: str, user_b: str) -> dict:
        a = user_a.strip().upper()
        b = user_b.strip().upper()
        if a == b:
            return {"status": "SELF"}
        friendships = self.get_all_friendships_for_user(a)
        for f in friendships:
            s = f["sender_roll"].upper()
            r = f["receiver_roll"].upper()
            if (s == a and r == b) or (s == b and r == a):
                if f["status"] == "ACCEPTED":
                    return {"status": "FRIENDS"}
                if s == a:
                    return {"status": "OUTGOING_PENDING"}
                return {"status": "INCOMING_PENDING"}
        return {"status": "NONE"}

    def send_friend_request(self, sender_roll: str, receiver_roll: str) -> dict:
        s = sender_roll.strip().upper()
        r = receiver_roll.strip().upper()
        rel = self.get_relationship(s, r)["status"]
        if rel in ("FRIENDS", "OUTGOING_PENDING"):
            return {"status": rel}
        if rel == "INCOMING_PENDING":
            return self.respond_friend_request(r, s, "ACCEPT")

        doc = {
            "sender_roll": s,
            "receiver_roll": r,
            "status": "PENDING",
            "created_at": iso_z(utc_now()),
        }
        if self.using_cloud:
            self.db.friendships.insert_one(dict(doc))
        else:
            data = self._read_local()
            data["friendships"].append(doc)
            self._write_local(data)
        return {"status": "OUTGOING_PENDING"}

    def respond_friend_request(
        self, sender_roll: str, receiver_roll: str, action: str
    ) -> dict:
        s = sender_roll.strip().upper()
        r = receiver_roll.strip().upper()
        act = action.strip().upper()
        if self.using_cloud:
            if act == "ACCEPT":
                self.db.friendships.update_one(
                    {"sender_roll": s, "receiver_roll": r},
                    {"$set": {"status": "ACCEPTED"}},
                )
                return {"status": "FRIENDS"}
            else:
                self.db.friendships.delete_one({"sender_roll": s, "receiver_roll": r})
                return {"status": "NONE"}
        else:
            data = self._read_local()
            if act == "ACCEPT":
                for f in data["friendships"]:
                    if f["sender_roll"].upper() == s and f["receiver_roll"].upper() == r:
                        f["status"] = "ACCEPTED"
                self._write_local(data)
                return {"status": "FRIENDS"}
            else:
                data["friendships"] = [
                    f
                    for f in data["friendships"]
                    if not (
                        f["sender_roll"].upper() == s
                        and f["receiver_roll"].upper() == r
                    )
                ]
                self._write_local(data)
                return {"status": "NONE"}

    def remove_friend(self, user_a: str, user_b: str):
        a = user_a.strip().upper()
        b = user_b.strip().upper()
        if self.using_cloud:
            self.db.friendships.delete_many(
                {
                    "$or": [
                        {"sender_roll": a, "receiver_roll": b},
                        {"sender_roll": b, "receiver_roll": a},
                    ]
                }
            )
        else:
            data = self._read_local()
            data["friendships"] = [
                f
                for f in data["friendships"]
                if not (
                    (f["sender_roll"].upper() == a and f["receiver_roll"].upper() == b)
                    or (
                        f["sender_roll"].upper() == b
                        and f["receiver_roll"].upper() == a
                    )
                )
            ]
            self._write_local(data)

    # ---------------- RAISE HAND (ACTIVE CHECK-INS) ----------------
    def get_active_hands(self) -> list[dict]:
        now = utc_now()
        if self.using_cloud:
            cursor = self.db.active_hands.find(
                {"expires_at_dt": {"$gt": now}}, {"_id": 0, "expires_at_dt": 0}
            )
            hands = list(cursor)
        else:
            data = self._read_local()
            hands = data.get("active_hands", [])

        enriched = []
        for h in hands:
            user = self.get_user(h["user_roll"])
            expires_dt = parse_iso(h["expires_at"])
            remaining_mins = max(0, int((expires_dt - now).total_seconds() // 60))
            enriched.append(
                {
                    **h,
                    "full_name": user["full_name"] if user else h["user_roll"],
                    "branch": user.get("branch", "") if user else "",
                    "hostel": user.get("hostel", "") if user else "",
                    "remaining_minutes": remaining_mins,
                    "needs_confirmation": remaining_mins <= 15,
                }
            )
        return enriched

    def get_user_hand(self, user_roll: str) -> dict | None:
        roll = user_roll.strip().upper()
        for h in self.get_active_hands():
            if h["user_roll"].upper() == roll:
                return h
        return None

    def raise_hand(
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
        hand_doc = {
            "user_roll": roll,
            "zone_name": zone_name,
            "room_id": room_id,
            "room_name": room_name,
            "note": note,
            "raised_at": iso_z(now),
            "expires_at": iso_z(expires),
        }
        if self.using_cloud:
            mongo_doc = {**hand_doc, "expires_at_dt": expires}
            self.db.active_hands.replace_one(
                {"user_roll": roll}, mongo_doc, upsert=True
            )
        else:
            data = self._read_local()
            data["active_hands"] = [
                h for h in data["active_hands"] if h["user_roll"].upper() != roll
            ]
            data["active_hands"].append(hand_doc)
            self._write_local(data)
        return self.get_user_hand(roll)

    def confirm_hand(self, user_roll: str, extend_minutes: int = 60) -> dict | None:
        roll = user_roll.strip().upper()
        current = self.get_user_hand(roll)
        if not current:
            return None
        now = utc_now()
        new_expires = now + timedelta(minutes=extend_minutes)
        if self.using_cloud:
            self.db.active_hands.update_one(
                {"user_roll": roll},
                {
                    "$set": {
                        "expires_at": iso_z(new_expires),
                        "expires_at_dt": new_expires,
                    }
                },
            )
        else:
            data = self._read_local()
            for h in data["active_hands"]:
                if h["user_roll"].upper() == roll:
                    h["expires_at"] = iso_z(new_expires)
            self._write_local(data)
        return self.get_user_hand(roll)

    def lower_hand(self, user_roll: str):
        roll = user_roll.strip().upper()
        if self.using_cloud:
            self.db.active_hands.delete_one({"user_roll": roll})
        else:
            data = self._read_local()
            data["active_hands"] = [
                h for h in data["active_hands"] if h["user_roll"].upper() != roll
            ]
            self._write_local(data)

    # ---------------- RSVPS (POKEMON GO STYLE LOBBIES) ----------------
    def get_rsvps(self, zone_name: str | None = None) -> list[dict]:
        if self.using_cloud:
            query = {"zone_name": zone_name} if zone_name else {}
            return list(self.db.rsvps.find(query, {"_id": 0}))
        data = self._read_local()
        rsvps = data.get("rsvps", [])
        if zone_name:
            return [r for r in rsvps if r["zone_name"] == zone_name]
        return rsvps

    def create_rsvp(
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

    def toggle_rsvp_participant(self, rsvp_id: str, user_roll: str) -> dict | None:
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
    def get_occupancy(self) -> dict:
        if self.using_cloud:
            doc = self.db.occupancy.find_one({"_id": "campus_live"}, {"_id": 0})
            if doc:
                return doc
        if OCCUPANCY_FILE.exists():
            with open(OCCUPANCY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"timestamp": iso_z(utc_now()), "zones": []}

    def save_occupancy(self, campus_data: dict):
        with open(OCCUPANCY_FILE, "w", encoding="utf-8") as f:
            json.dump(campus_data, f, indent=4)
        if self.using_cloud:
            doc = {**campus_data, "_id": "campus_live"}
            self.db.occupancy.replace_one({"_id": "campus_live"}, doc, upsert=True)

    def update_room_seats(
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
