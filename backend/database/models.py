from pydantic import BaseModel,Field

class Seat(BaseModel):
    id: str
    vacant: bool
    
    


class Room(BaseModel):
    id : str
    name: str
    Total_Seats : int
    seats : list[Seat] = Field(Default_factory=list)




