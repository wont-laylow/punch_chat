"""
Unit tests for Pydantic schemas to ensure validation works.
"""

import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate
from app.schemas.auth import LoginRequest, TokenPair
from app.schemas.chat import ChatRoomCreate, MessageCreate
from app.models.chat import RoomType


def test_user_create_valid():
    """Test valid UserCreate schema."""
    user_data = UserCreate(
        email="user@example.com",
        username="testuser",
        password="SecurePass123!",
    )
    assert user_data.email == "user@example.com"
    assert user_data.username == "testuser"


def test_user_create_password_too_short():
    """Test that UserCreate rejects short passwords."""
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            email="user@example.com",
            username="testuser",
            password="short",
        )
    assert "password" in str(exc_info.value).lower()


def test_login_request_valid():
    """Test valid LoginRequest schema."""
    login = LoginRequest(email="user@example.com", password="password123")
    assert login.email == "user@example.com"
    assert login.password == "password123"


def test_token_pair_valid():
    """Test TokenPair schema."""
    tokens = TokenPair(
        access_token="access_xyz",
        refresh_token="refresh_xyz",
        token_type="bearer",
    )
    assert tokens.token_type == "bearer"


def test_chat_room_create_direct():
    """Test ChatRoomCreate for direct rooms."""
    room_data = ChatRoomCreate(
        name="Direct Chat",
        room_type=RoomType.DIRECT,
        member_ids=["1", "2"],
    )
    assert room_data.room_type == RoomType.DIRECT


def test_message_create_valid():
    """Test MessageCreate schema."""
    msg = MessageCreate(room_id=1, content="Hello")
    assert msg.room_id == 1
    assert msg.content == "Hello"
