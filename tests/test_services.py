import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.chat import ChatRoom, RoomMembership, Message, RoomType
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRoomCreate, MessageCreate


class MockAsyncSession:
    """Mock AsyncSession for testing without a real database."""

    def __init__(self):
        self.users = {}
        self.rooms = {}
        self.memberships = {}
        self.messages = {}
        self._id_counter = {"user": 0, "room": 0, "membership": 0, "message": 0}

    async def execute(self, stmt):
        # Simple mock: return self for select queries
        return self

    def scalars(self):
        return self

    def first(self):
        # Return mocked results based on statement
        return None

    def unique(self):
        return self

    def add(self, obj):
        # Mock add
        if isinstance(obj, User):
            self._id_counter["user"] += 1
            obj.id = self._id_counter["user"]
            self.users[obj.id] = obj
        elif isinstance(obj, ChatRoom):
            self._id_counter["room"] += 1
            obj.id = self._id_counter["room"]
            obj.is_active = True
            self.rooms[obj.id] = obj
        elif isinstance(obj, RoomMembership):
            self._id_counter["membership"] += 1
            obj.id = self._id_counter["membership"]
            self.memberships[obj.id] = obj
        elif isinstance(obj, Message):
            self._id_counter["message"] += 1
            obj.id = self._id_counter["message"]
            if not hasattr(obj, 'created_at') or obj.created_at is None:
                obj.created_at = datetime.utcnow()
            self.messages[obj.id] = obj

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.mark.asyncio
async def test_create_room_direct():
    """Test creating a direct chat room."""
    service = ChatService()
    db = MockAsyncSession()

    # Mock users
    user1 = User(id=1, email="a@test.com", username="user_a", hashed_password="x")
    user2 = User(id=2, email="b@test.com", username="user_b", hashed_password="x")

    data = ChatRoomCreate(
        name="Direct Chat",
        room_type=RoomType.DIRECT,
        member_ids=["1", "2"],
    )

    # Pass current_user_id as string to match the schema
    room = await service.create_room(db, data, current_user_id="1")

    assert room.room_type == RoomType.DIRECT
    assert room.is_active is True


@pytest.mark.asyncio
async def test_create_room_group():
    """Test creating a group chat room."""
    service = ChatService()
    db = MockAsyncSession()

    data = ChatRoomCreate(
        name="Group Chat",
        room_type=RoomType.GROUP,
        member_ids=["1", "2", "3"],
    )

    room = await service.create_room(db, data, current_user_id="1")

    assert room.room_type == RoomType.GROUP
    assert room.name == "Group Chat"


@pytest.mark.asyncio
async def test_save_message():
    """Test saving a message to the database."""
    service = ChatService()
    db = MockAsyncSession()

    msg_in = MessageCreate(room_id=1, content="Hello, World!")
    msg, block_reason = await service.save_message(db, message_in=msg_in, sender_id=5)

    assert msg is not None
    assert block_reason is None
    assert msg.room_id == 1
    assert msg.sender_id == 5
    assert msg.content == "Hello, World!"
    assert hasattr(msg, 'created_at')
