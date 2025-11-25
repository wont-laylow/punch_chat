from typing import List, Optional, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatRoom, RoomMembership, Message, RoomType
from app.schemas.chat import ChatRoomCreate, MessageCreate
from app.models.user import User
from app.core.logger import get_logger
from app.ai.moderator import check_message_allowed

logger = get_logger(__name__)


class ChatService:
    async def create_room(
        self,
        db: AsyncSession,
        data: ChatRoomCreate,
        current_user_id: int,
    ) -> ChatRoom:
        """
        Create a new room (direct or group) and add members.

        - For DIRECT: must have exactly 2 members.
        - For GROUP: at least 2 members.
        """
        members = list(set(data.member_ids))

        if current_user_id not in members:
            members.append(current_user_id)

        if data.room_type == RoomType.DIRECT:
            if len(members) != 2:
                raise ValueError("Direct room must have exactly 2 distinct members.")
        else:
            if len(members) < 2:
                raise ValueError("Group room must have at least 2 members.")

        room = ChatRoom(
            name=data.name,
            room_type=data.room_type,
        )
        db.add(room)
        await db.flush()

        logger.info("Created room (type=%s) provisional id=%s with members=%s", data.room_type, getattr(room, 'id', None), members)

        for uid in members:
            membership = RoomMembership(room_id=room.id, user_id=uid)
            db.add(membership)

        await db.commit()
        await db.refresh(room)
        logger.info("Room created id=%s type=%s", room.id, room.room_type)
        return room

    async def get_room_for_user(
        self,
        db: AsyncSession,
        room_id: int,
        user_id: int,
    ) -> Optional[ChatRoom]:
        """
        Return room if user is a member, else None.
        Used for both HTTP and WebSocket.
        """
        stmt = (
            select(ChatRoom)
            .join(RoomMembership, RoomMembership.room_id == ChatRoom.id)
            .where(
                and_(
                    ChatRoom.id == room_id,
                    RoomMembership.user_id == user_id,
                    ChatRoom.is_active.is_(True),
                )
            )
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    async def get_user_rooms(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> List[ChatRoom]:
        """
        List all rooms the user belongs to.
        """
        stmt = (
            select(ChatRoom)
            .join(RoomMembership, RoomMembership.room_id == ChatRoom.id)
            .where(RoomMembership.user_id == user_id, ChatRoom.is_active.is_(True))
        )
        res = await db.execute(stmt)
        return list(res.scalars().unique())
    
    async def get_or_create_direct_room(
        self,
        db: AsyncSession,
        user_a_id: int,
        user_b_id: int,
    ) -> ChatRoom:
        """
        Get an existing DIRECT room between two users, or create one.

        A direct room is defined as:
        - room_type = DIRECT
        - has exactly 2 memberships: user_a and user_b
        """
        # Ensure consistent ordering (1,2) same as (2,1)
        user_ids = sorted([user_a_id, user_b_id])

        # Find a DIRECT room where both users are members and there are exactly 2 members
        subq = (
            select(RoomMembership.room_id)
            .join(ChatRoom, ChatRoom.id == RoomMembership.room_id)
            .where(
                ChatRoom.room_type == RoomType.DIRECT,
                RoomMembership.user_id.in_(user_ids),
            )
            .group_by(RoomMembership.room_id, ChatRoom.id)
            .having(func.count(RoomMembership.user_id) == 2)
        )

        res = await db.execute(subq)
        existing_room_id = res.scalars().first()

        if existing_room_id:
            # Fetch and return that room
            stmt = select(ChatRoom).where(ChatRoom.id == existing_room_id)
            room_res = await db.execute(stmt)
            logger.info("Found existing direct room id=%s for users %s", existing_room_id, user_ids)
            return room_res.scalars().first()

        # Otherwise create a new direct room
        room = ChatRoom(
            name=None,
            room_type=RoomType.DIRECT,
        )
        db.add(room)
        await db.flush()

        for uid in user_ids:
            db.add(RoomMembership(room_id=room.id, user_id=uid))

        await db.commit()
        await db.refresh(room)
        logger.info("Created new direct room id=%s for users %s", room.id, user_ids)
        return room

    async def add_member_to_group(
        self,
        db: AsyncSession,
        room_id: int,
        new_username: str,
        acting_user_id: int,
    ) -> ChatRoom:
        """
        Add a user (by username) to an existing GROUP room.

        - acting_user_id must already be a member of the room
        - room must be a group
        - new user must exist and not already be a member
        """
        # Load room and memberships
        from app.models.chat import ChatRoom, RoomMembership, RoomType  # avoid circular

        result = await db.execute(
            select(ChatRoom).where(ChatRoom.id == room_id)
        )
        room = result.scalars().first()
        if not room:
            raise ValueError("Room not found")

        room_type = room.room_type.value if hasattr(room.room_type, "value") else room.room_type
        if room_type != "group":
            raise ValueError("Can only add members to group rooms")

        # Ensure acting user is member
        result = await db.execute(
            select(RoomMembership).where(
                RoomMembership.room_id == room_id,
                RoomMembership.user_id == acting_user_id,
            )
        )
        acting_membership = result.scalars().first()
        if not acting_membership:
            raise ValueError("You are not a member of this room")

        # Find the user by username
        result = await db.execute(
            select(User).where(User.username == new_username)
        )
        new_user = result.scalars().first()
        if not new_user:
            raise ValueError("User not found")

        # Check if already member
        result = await db.execute(
            select(RoomMembership).where(
                RoomMembership.room_id == room_id,
                RoomMembership.user_id == new_user.id,
            )
        )
        existing = result.scalars().first()
        if existing:
            raise ValueError("User is already a member of this room")

        membership = RoomMembership(
            room_id=room_id,
            user_id=new_user.id,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(room)
        logger.info("Added user id=%s to room id=%s by acting_user=%s", new_user.id, room_id, acting_user_id)
        return room

    async def save_message(
        self,
        db: AsyncSession,
        message_in: MessageCreate,
        sender_id: int,
    ) -> tuple[Optional[Message], Optional[str]]:
        """
        Persist a message in the DB after checking content moderation.
        Returns: (message: Optional[Message], block_reason: Optional[str])
        - If blocked, returns (None, reason)
        - If allowed, returns (message_obj, None)
        """
        logger.debug("Checking message content: %s", message_in.content[:50])
        try:
            allowed, block_reason = await check_message_allowed(message_in.content)
            logger.debug("Moderation result - Allowed: %s, Reason: %s", allowed, block_reason)
        except Exception as e:
            logger.error("Error during moderation check: %s", e, exc_info=True)
            allowed = True
            block_reason = None
        
        if not allowed:
            logger.warning("Message blocked: %s | Reason: %s", message_in.content[:50], block_reason)
            return None, block_reason
        
        logger.debug("Message passed moderation check")
        message = Message(
            room_id=message_in.room_id,
            sender_id=sender_id,
            content=message_in.content,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        logger.debug("Persisted message id=%s room=%s sender=%s", message.id, message.room_id, message.sender_id)
        return message, None

    async def get_room_messages(
        self,
        db: AsyncSession,
        room_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Message]:
        """
        Fetch messages for a room, newest first, paginated.
        """
        stmt = (
            select(Message)
            .where(Message.room_id == room_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(stmt)
        return list(res.scalars())
