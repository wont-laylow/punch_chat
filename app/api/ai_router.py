from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.db import get_db
from app.api.deps import get_current_user
from app.models.chat import ChatRoom, RoomMembership, Message
from app.models.user import User
from app.ai.summarizer import summarize_messages


class SummaryRequest(BaseModel):
    max_messages: int = 100
    style: str = "short"


class SummaryResponse(BaseModel):
    room_id: int
    summary: str
    used_messages: int


ai_router = APIRouter(prefix="/ai", tags=["ai"])


@ai_router.post(
    "/summary/rooms/{room_id}",
    response_model=SummaryResponse,
)
async def summarize_room(
    room_id: int,
    body: SummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Validate user is member of room
    stmt_room = (
        select(ChatRoom)
        .join(RoomMembership, RoomMembership.room_id == ChatRoom.id)
        .where(
            ChatRoom.id == room_id,
            RoomMembership.user_id == current_user.id,
        )
    )
    res_room = await db.execute(stmt_room)
    room = res_room.scalars().first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found or you are not a member",
        )

    # 2. Load last N messages with sender
    limit = min(max(body.max_messages, 1), 500)  # clamp 1–500
    stmt_msgs = (
        select(Message)
        .options(joinedload(Message.sender))
        .where(Message.room_id == room_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    res_msgs = await db.execute(stmt_msgs)
    msgs = list(res_msgs.scalars().all())
    msgs.reverse()  # oldest → newest

    # 3. Prepare (username, content) list
    chat_pairs = []
    for m in msgs:
        if not m.sender:
            continue
        chat_pairs.append((m.sender.username, m.content))

    # 4. Call OpenAI summarizer
    summary = await summarize_messages(chat_pairs, style=body.style)

    return SummaryResponse(
        room_id=room_id,
        summary=summary,
        used_messages=len(chat_pairs),
    )
