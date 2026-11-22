from pydantic import BaseModel


class Camera(BaseModel):
    camera_id: str
    room_id: str
    source_type: str = "webcam"  # "webcam" | "rtsp" | "image"
    source: str = "0"
    reference_width: int = 1280
    reference_height: int = 720
