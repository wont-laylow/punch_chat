from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.chat import RoomType


class ChatRoomCreate(BaseModel):
    """Payload to create a new chat room (direct or group)."""
    name: Optional[str] = None
    room_type: RoomType
    member_ids: List[str]


class ChatRoomRead(BaseModel):
    """Room info returned to the client."""
    id: int
    name: Optional[str]
    room_type: RoomType

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    """Body for creating/saving a message (used internally)."""
    room_id: int
    content: str


class MessageRead(BaseModel):
    """Message representation returned to client."""
    id: int
    room_id: int
    sender_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
