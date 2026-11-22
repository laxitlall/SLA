from pydantic import BaseModel, Field


class Library(BaseModel):
    library_id: str
    name: str
    campus: str = "IIT Bombay"
    floors: list[int] = Field(default_factory=list)
    is_active: bool = True
