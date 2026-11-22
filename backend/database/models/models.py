from typing import Optional
from pydantic import BaseModel, Field


class SeatDetection(BaseModel):
    person: bool = False
    laptop: bool = False
    bag: bool = False


class Seat(BaseModel):
    seat_id: str
    detections: SeatDetection = Field(default_factory=SeatDetection)
    computed_state: str = "AVAILABLE"  # AVAILABLE | SPOT_HELD | OCCUPIED
    confidence_score: float = 0.95


class Room(BaseModel):
    room_id: str
    room_name: str
    seats: list[Seat] = Field(default_factory=list)


class Zone(BaseModel):
    zone_type: str  # "hostel" | "library"
    name: str
    rooms: list[Room] = Field(default_factory=list)


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
