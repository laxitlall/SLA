from pydantic import BaseModel,Field

class Seat(BaseModel):
    id: int
    bag_present: bool
    person_present: bool
    laptop_present: bool
    vacant: bool
    

    
    


class Room(BaseModel):
    id : str
    library_id: str
    name: str
    capacity: int
    floor: int
    root_type: int
    is_open: bool
    seats: list[Seat] = Field(default_factory=list)

