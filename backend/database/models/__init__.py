from typing import Optional
from pydantic import BaseModel

from .camera import Camera
from .libraries import Library
from .room import Room, Seat, SeatDetection, Zone


class SignupRequest(BaseModel):
    full_name: str
    roll_number: str
    email: str
    password: str
    branch: str = "Computer Science"
    hostel: str = "Hostel 4"


class LoginRequest(BaseModel):
    roll_number: str
    password: str


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    branch: Optional[str] = None
    hostel: Optional[str] = None
    bio: Optional[str] = None


class FriendRequestCreate(BaseModel):
    sender_roll: str
    receiver_roll: str


class FriendRequestRespond(BaseModel):
    sender_roll: str
    receiver_roll: str
    action: str  # "ACCEPT" | "DECLINE"


class RaiseHandRequest(BaseModel):
    user_roll: str
    zone_name: str
    room_id: str
    room_name: str
    note: str = "Studying for exams"
    duration_minutes: int = 120


class ConfirmHandRequest(BaseModel):
    user_roll: str
    extend_minutes: int = 60


class RSVPCreateRequest(BaseModel):
    creator_roll: str
    zone_name: str
    room_id: str
    room_name: str
    start_time: str
    end_time: str
    topic: str = "Group Study Session"


class RSVPToggleRequest(BaseModel):
    user_roll: str


class RoomDetectRequest(BaseModel):
    zone_name: str = "Central Library"
    room_id: str = "central-lib-room-1"
    image_path: Optional[str] = None
    camera_source: Optional[str] = None


__all__ = [
    "Camera",
    "Library",
    "SeatDetection",
    "Seat",
    "Room",
    "Zone",
    "SignupRequest",
    "LoginRequest",
    "ProfileUpdateRequest",
    "FriendRequestCreate",
    "FriendRequestRespond",
    "RaiseHandRequest",
    "ConfirmHandRequest",
    "RSVPCreateRequest",
    "RSVPToggleRequest",
    "RoomDetectRequest",
]
