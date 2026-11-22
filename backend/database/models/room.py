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
    # Optional fields for compatibility with room schema
    id: Optional[int] = None
    bag_present: Optional[bool] = None
    person_present: Optional[bool] = None
    laptop_present: Optional[bool] = None
    vacant: Optional[bool] = None


class Room(BaseModel):
    room_id: str
    room_name: str
    seats: list[Seat] = Field(default_factory=list)
    library_id: Optional[str] = None
    capacity: Optional[int] = None
    floor: Optional[int] = 1
    room_type: str = "study_room"
    is_open: bool = True


class Zone(BaseModel):
    zone_type: str  # "hostel" | "library"
    name: str
    rooms: list[Room] = Field(default_factory=list)
