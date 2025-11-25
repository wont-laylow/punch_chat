from typing import List
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRoomCreate, ChatRoomRead, MessageRead
from app.services.chat_service import ChatService


class AddMemberRequest(BaseModel):
    user_name: str


class ChatRouter:
    """
    APIRouter for chat endpoints.
    """

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/chat",
            tags=["chat"],
        )
        self.service = ChatService()
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.post("/rooms", response_model=ChatRoomRead)(self.create_room)
        self.router.get("/rooms", response_model=List[ChatRoomRead])(self.list_rooms)
        self.router.get(
            "/rooms/{room_id}/messages",
            response_model=List[MessageRead],
        )(self.get_messages)
        self.router.post(
            "/direct/{other_user_id}",
            response_model=ChatRoomRead,
        )(self.open_direct_chat)
        self.router.post(
            "/rooms/{room_id}/members",
            response_model=ChatRoomRead,
        )(self.add_member)

    async def add_member(
        self,
        room_id: int,
        body: AddMemberRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """
        Add a user (by username) to an existing GROUP chat.
        The current user must already be a member of that group.
        """
        try:
            room = await self.service.add_member_to_group(
                db,
                room_id=room_id,
                new_username=body.username,
                acting_user_id=current_user.id,
            )
            return room
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    async def create_room(
        self,
        data: ChatRoomCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """
        Create a direct or group room.
        For group rooms, 'member_usernames' will be used to look up users.
        """
        try:
            room = await self.service.create_room(
                db,
                data,
                current_user_id=current_user.id,
            )
            return room
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    async def open_direct_chat(
        self,
        other_user_id: int = Path(..., description="The user to DM"),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """
        Get or create a direct (1–1) room between current_user and other_user_id.
        Direct chats still use user_id because they come from explicit search results.
        """
        if other_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot start a direct chat with yourself",
            )

        room = await self.service.get_or_create_direct_room(
            db,
            user_a_id=current_user.id,
            user_b_id=other_user_id,
        )
        return room

    async def list_rooms(
        self,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """
        List all rooms current user belongs to.
        """
        rooms = await self.service.get_user_rooms(db, current_user.id)
        return rooms

    async def get_messages(
        self,
        room_id: int,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """
        Fetch recent messages for a room the user belongs to.
        """
        room = await self.service.get_room_for_user(db, room_id, current_user.id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found or you are not a member",
            )

        messages = await self.service.get_room_messages(db, room_id, limit, offset)
        return messages