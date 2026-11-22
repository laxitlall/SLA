from pydantic import BaseModel,Field

class Library(BaseModel): 
    library_id: str
    name: str
    campus: str
    floors: list[int] = Field(default_factory=list)
    is_active: bool

