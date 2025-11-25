from pydantic import BaseModel

class SummaryRequest(BaseModel):
    max_messages: int = 100
    style: str = "short"


class SummaryResponse(BaseModel):
    room_id: int
    summary: str
    used_messages: int