from typing import List
from sqlalchemy.orm import joinedload


from app.security.security import (
    verify_password,
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    create_password_reset_token,
    validate_password_reset_token,
)

from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.config import settings
from app.core.logger import get_logger
from app.models.user import User
from app.models.chat import ChatRoom, RoomMembership, RoomType, Message
from app.security.security import verify_password, create_jwt_token, decode_jwt_token
from app.services.chat_service import ChatService
from app.schemas.chat import MessageCreate

templates = Jinja2Templates(directory="app/templates")
logger = get_logger(__name__)

web_router = APIRouter(prefix="/web", tags=["web"])
chat_service = ChatService()


# Helpers 

async def get_user_from_cookie(
    request: Request,
    db: AsyncSession,
) -> User:
    """
    Read JWT access token from the 'access_token' cookie,
    validate it, and return the current user.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_jwt_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or missing user",
        )

    return user


# ---------- routes ----------

@web_router.get("/login", response_class=HTMLResponse)
async def web_login_page(request: Request):
    """
    Show login form. If already logged in, redirect to chats.
    """
    # check for cookie existing 

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "project_name": settings.PROJECT_NAME,
            "error": None,
        },
    )


@web_router.post("/login", response_class=HTMLResponse)
async def web_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Process login form, set cookie, redirect to chats.
    """
    # Authenticate like /auth/login
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalars().first()

    if not user or not verify_password(password, user.hashed_password):
        # Re-render login page with error
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "project_name": settings.PROJECT_NAME,
                "error": "Incorrect email or password",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Create access token (same as API)
    from datetime import timedelta

    access_token = create_jwt_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )

    response = RedirectResponse(
        url="/web/chats",
        status_code=status.HTTP_302_FOUND,
    )
    # Dev settings: HttpOnly cookie, not Secure (because localhost)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@web_router.get("/logout")
async def web_logout():
    """
    Clear auth cookie and go back to login page.
    """
    response = RedirectResponse(url="/web/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response


@web_router.get("/register", response_class=HTMLResponse)
async def web_register_page(request: Request):
    """
    Show the registration form.
    """
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "project_name": settings.PROJECT_NAME,
            "error": None,
        },
    )


@web_router.post("/register", response_class=HTMLResponse)
async def web_register_submit(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle registration form, create user in DB, then redirect to login.
    """
    # Check for existing user (email OR username)
    existing_q = select(User).where(
        (User.email == email) | (User.username == username)
    )
    res = await db.execute(existing_q)
    existing = res.scalars().first()

    if existing:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "project_name": settings.PROJECT_NAME,
                "error": "Email or username already taken",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Create new user
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # After successful registration, redirect to login page
    response = RedirectResponse(
        url="/web/login",
        status_code=status.HTTP_302_FOUND,
    )
    return response


@web_router.get("/chats", response_class=HTMLResponse)
async def web_chats_page(
    request: Request,
    q: str | None = None,  # optional search query
    db: AsyncSession = Depends(get_db),
):
    """
    Show list of conversations (rooms) for the current user.
    Also optionally show search results for starting a new chat.
    """
    user = await get_user_from_cookie(request, db)

    # --- existing conversations ---
    stmt = (
        select(ChatRoom)
        .join(RoomMembership, RoomMembership.room_id == ChatRoom.id)
        .where(RoomMembership.user_id == user.id)
        .order_by(ChatRoom.id.desc())
    )
    res = await db.execute(stmt)
    rooms: list[ChatRoom] = res.scalars().all()

    conversations = []
    for room in rooms:
        label = room.name or f"Room {room.id}"
        room_type_str = getattr(room.room_type, "value", room.room_type)

        # For direct chats, show the other user's username as label
        if room_type_str == "direct":
            stmt_other = (
                select(User)
                .join(RoomMembership, RoomMembership.user_id == User.id)
                .where(
                    RoomMembership.room_id == room.id,
                    User.id != user.id,
                )
            )
            res_other = await db.execute(stmt_other)
            other_user = res_other.scalars().first()
            if other_user:
                label = other_user.username

        conversations.append(
            {
                "id": room.id,
                "label": label,
                "room_type": room_type_str,
            }
        )

    # --- user search (for starting a new chat) ---
    search_results: list[User] = []
    if q:
        stmt_users = (
            select(User)
            .where(User.username.ilike(f"%{q}%"))
            .limit(20)
        )
        res_users = await db.execute(stmt_users)
        users_found = res_users.scalars().all()
        # don't show yourself in search results
        search_results = [u for u in users_found if u.id != user.id]

    return templates.TemplateResponse(
        "chat_list.html",
        {
            "request": request,
            "user": user,
            "conversations": conversations,
            "search_query": q or "",
            "search_results": search_results,
        },
    )

@web_router.get("/chats", response_class=HTMLResponse)
async def web_chats_page(
    request: Request,
    q: str | None = None,  # optional search query
    db: AsyncSession = Depends(get_db),
):
    """
    Show list of conversations (rooms) for the current user.
    Also optionally show search results for starting a new chat.
    """
    user = await get_user_from_cookie(request, db)

    # --- existing conversations ---
    stmt = (
        select(ChatRoom)
        .join(RoomMembership, RoomMembership.room_id == ChatRoom.id)
        .where(RoomMembership.user_id == user.id)
        .order_by(ChatRoom.id.desc())
    )
    res = await db.execute(stmt)
    rooms: list[ChatRoom] = res.scalars().all()

    conversations = []
    for room in rooms:
        label = room.name or f"Room {room.id}"
        room_type_str = getattr(room.room_type, "value", room.room_type)

        # For direct chats, show the other user's username as label
        if room_type_str == "direct":
            stmt_other = (
                select(User)
                .join(RoomMembership, RoomMembership.user_id == User.id)
                .where(
                    RoomMembership.room_id == room.id,
                    User.id != user.id,
                )
            )
            res_other = await db.execute(stmt_other)
            other_user = res_other.scalars().first()
            if other_user:
                label = other_user.username

        conversations.append(
            {
                "id": room.id,
                "label": label,
                "room_type": room_type_str,
            }
        )

    # --- user search (for starting a new chat) ---
    search_results: list[User] = []
    if q:
        stmt_users = (
            select(User)
            .where(User.username.ilike(f"%{q}%"))
            .limit(20)
        )
        res_users = await db.execute(stmt_users)
        users_found = res_users.scalars().all()
        # don't show yourself in search results
        search_results = [u for u in users_found if u.id != user.id]

    return templates.TemplateResponse(
        "chat_list.html",
        {
            "request": request,
            "user": user,
            "conversations": conversations,
            "search_query": q or "",
            "search_results": search_results,
        },
    )


@web_router.post("/chats/direct")
async def web_start_direct_chat(
    request: Request,
    other_user_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a direct chat room between current user and another user,
    then redirect to that room.
    """
    current_user = await get_user_from_cookie(request, db)

    # Ensure other user exists
    res_other = await db.execute(select(User).where(User.id == other_user_id))
    other_user = res_other.scalars().first()
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # For simplicity, always create a new direct room
    # (You could add de-duplication later if you want)
    try:
        room_type_val = RoomType.DIRECT
    except AttributeError:
        room_type_val = "direct"

    room = ChatRoom(
        room_type=room_type_val,
        name=None,
    )
    db.add(room)
    await db.flush()  # get room.id

    # memberships
    db.add_all(
        [
            RoomMembership(user_id=current_user.id, room_id=room.id),
            RoomMembership(user_id=other_user.id, room_id=room.id),
        ]
    )
    await db.commit()

    return RedirectResponse(
        url=f"/web/chats/{room.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@web_router.post("/chats/group")
async def web_create_group(
    request: Request,
    group_name: str = Form(""),
    member_usernames: str = Form(""),  # comma-separated usernames
    db: AsyncSession = Depends(get_db),
):
    """
    Create a group room using usernames instead of IDs.
    The current user is always included as a member.
    """
    current_user = await get_user_from_cookie(request, db)

    # Parse comma-separated usernames ("alice,bob,charlie")
    usernames = set()
    if member_usernames.strip():
        for part in member_usernames.split(","):
            part = part.strip()
            if part:
                usernames.add(part)

    # Look up users by username
    users = []
    if usernames:
        result = await db.execute(
            select(User).where(User.username.in_(usernames))
        )
        users = list(result.scalars().all())

        found_usernames = {u.username for u in users}
        missing = usernames - found_usernames
        if missing:
            # Simple error for now; you could re-render template with error instead
            raise HTTPException(
                status_code=400,
                detail=f"These users were not found: {', '.join(sorted(missing))}",
            )

    # Determine room_type value from enum or str
    try:
        room_type_val = RoomType.GROUP
    except AttributeError:
        room_type_val = "group"

    # Create the room
    room = ChatRoom(
        room_type=room_type_val,
        name=group_name or None,
    )
    db.add(room)
    await db.flush()  # get room.id

    # Build memberships always includeing current user
    memberships = [RoomMembership(user_id=current_user.id, room_id=room.id)]
    for u in users:
        if u.id != current_user.id:
            memberships.append(RoomMembership(user_id=u.id, room_id=room.id))

    db.add_all(memberships)
    await db.commit()

    return RedirectResponse(
        url=f"/web/chats/{room.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@web_router.get("/chats/{room_id}", response_class=HTMLResponse)
async def web_chat_room_page(
    room_id: int,
    request: Request,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_cookie(request, db)

    stmt_room = (
        select(ChatRoom)
        .join(RoomMembership, RoomMembership.room_id == ChatRoom.id)
        .where(
            ChatRoom.id == room_id,
            RoomMembership.user_id == user.id,
        )
    )
    res_room = await db.execute(stmt_room)
    room = res_room.scalars().first()
    if not room:
        return RedirectResponse("/web/chats", status_code=status.HTTP_302_FOUND)

    label = room.name or f"Room {room.id}"
    room_type_str = getattr(room.room_type, "value", room.room_type)

    if room_type_str == "direct":
        stmt_other = (
            select(User)
            .join(RoomMembership, RoomMembership.user_id == User.id)
            .where(
                RoomMembership.room_id == room.id,
                User.id != user.id,
            )
        )
        res_other = await db.execute(stmt_other)
        other = res_other.scalars().first()
        if other:
            label = other.username

    stmt_msgs = (
        select(Message)
        .options(joinedload(Message.sender))
        .where(Message.room_id == room.id)
        .order_by(Message.created_at.asc())
        .limit(100)
    )
    res_msgs = await db.execute(stmt_msgs)
    messages = res_msgs.scalars().all()

    # read access_token cookie to use for WebSocket
    ws_token = request.cookies.get("access_token")

    return templates.TemplateResponse(
        "chat_room.html",
        {
            "request": request,
            "user": user,
            "room": room,
            "room_label": label,
            "room_type": room_type_str,
            "messages": messages,
            "ws_token": ws_token,
            "error": error,
        },
    )


@web_router.post("/chats/{room_id}/send")
async def web_chat_room_send(
    room_id: int,
    request: Request,
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a new message to this room via HTTP (not WebSocket).
    Just saves to DB; your existing WebSocket can still broadcast separately.
    """
    user = await get_user_from_cookie(request, db)

    # Ensure membership
    stmt_room = (
        select(ChatRoom)
        .join(RoomMembership, RoomMembership.room_id == ChatRoom.id)
        .where(
            ChatRoom.id == room_id,
            RoomMembership.user_id == user.id,
        )
    )
    res_room = await db.execute(stmt_room)
    room = res_room.scalars().first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found or no access",
        )

    # Check message content with moderator
    msg_create = MessageCreate(room_id=room_id, content=content)
    msg, block_reason = await chat_service.save_message(
        db,
        message_in=msg_create,
        sender_id=user.id,
    )
    
    # If message was blocked, show error to user
    if block_reason:
        logger.warning("Message blocked for user %s: %s", user.id, block_reason)
        # Fetch room messages to display
        stmt_msgs = (
            select(Message)
            .where(Message.room_id == room_id)
            .order_by(Message.created_at.asc())
            .limit(100)
            .options(joinedload(Message.sender))
        )
        res_msgs = await db.execute(stmt_msgs)
        messages = list(res_msgs.scalars().unique())
        
        # Render the chat room page again with error message
        room_type = "Direct" if room.room_type == RoomType.DIRECT else "Group"
        room_label = room.name or f"{room_type} Chat"
        
        return templates.TemplateResponse(
            "chat_room.html",
            {
                "request": request,
                "room": room,
                "room_type": room_type,
                "room_label": room_label,
                "messages": messages,
                "user": user,
                "ws_token": None,
                "error": f"❌ Message blocked: {block_reason}",
            }
        )

    # TODO: if you want true realtime, call your ConnectionManager.broadcast here.

    # Redirect back to room page (PRG pattern)
    return RedirectResponse(
        url=f"/web/chats/{room_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@web_router.get("/password-reset", response_class=HTMLResponse)
async def password_reset_request_page(request: Request):
    """
    Show password reset request form (asks for email).
    """
    return templates.TemplateResponse(
        "password_reset_request.html",
        {
            "request": request,
            "project_name": settings.PROJECT_NAME,
            "error": None,
        },
    )


@web_router.post("/password-reset", response_class=HTMLResponse)
async def password_reset_request_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle password reset request form submission.
    Returns a page with the reset token or error message.
    """
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalars().first()

    if not user:
        logger.info("Password reset requested for non-existent email=%s", email)
        return templates.TemplateResponse(
            "password_reset_request.html",
            {
                "request": request,
                "project_name": settings.PROJECT_NAME,
                "success": "If an account exists with that email, a reset link has been sent.",
            },
        )

    from datetime import timedelta
    reset_token = create_password_reset_token(user.id, expires_delta=timedelta(hours=1))

    logger.info("Password reset initiated for user=%s (email=%s)", user.id, user.email)

    return templates.TemplateResponse(
        "password_reset_form.html",
        {
            "request": request,
            "project_name": settings.PROJECT_NAME,
            "token": reset_token,
            "error": None,
        },
    )


@web_router.post("/password-reset/confirm", response_class=HTMLResponse)
async def password_reset_confirm(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle password reset form submission (validate token and update password).
    """
    if password != confirm:
        return templates.TemplateResponse(
            "password_reset_form.html",
            {
                "request": request,
                "project_name": settings.PROJECT_NAME,
                "token": token,
                "error": "Passwords do not match",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user_id = validate_password_reset_token(token)

    if not user_id:
        logger.warning("Password reset attempted with invalid token")
        return templates.TemplateResponse(
            "password_reset_request.html",
            {
                "request": request,
                "project_name": settings.PROJECT_NAME,
                "error": "Invalid or expired reset token. Please request a new one.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()

    if not user or not user.is_active:
        logger.warning("Password reset attempted for inactive user: user_id=%s", user_id)
        return templates.TemplateResponse(
            "password_reset_request.html",
            {
                "request": request,
                "project_name": settings.PROJECT_NAME,
                "error": "User account is not active",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.hashed_password = hash_password(password)
    await db.commit()

    logger.info("Password reset successful for user=%s (email=%s)", user.id, user.email)

    return templates.TemplateResponse(
        "password_reset_success.html",
        {
            "request": request,
            "project_name": settings.PROJECT_NAME,
        },
    )
