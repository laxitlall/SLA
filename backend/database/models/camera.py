
from pydantic import BaseModel,Field

class Camera(BaseModel): 
    camera_id: bool
    room_id: bool
    sorce_type: str
    reference_width: int
    reference_height: int