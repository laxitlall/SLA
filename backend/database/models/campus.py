from pydantic import BaseModel, Field

from .room import Zone


class CampusOccupancy(BaseModel):
    """Shape of the single live occupancy document (timestamp + zones -> rooms -> seats)."""

    timestamp: str
    zones: list[Zone] = Field(default_factory=list)
