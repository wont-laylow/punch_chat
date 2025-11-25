from typing import List

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.db import get_db
from app.core.config import settings
from app.models.user import User
from app.models.chat import ChatRoom, Message, RoomMembership
from app.api.deps import get_current_admin

templates = Jinja2Templates(directory="app/templates")

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Simple admin dashboard with some stats.
    """
    # total users
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.is_active == True))
    ).scalar_one()
    admin_users = (
        await db.execute(select(func.count(User.id)).where(User.is_admin == True))
    ).scalar_one()

    # rooms and messages
    total_rooms = (await db.execute(select(func.count(ChatRoom.id)))).scalar_one()
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar_one()

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "admin": admin,
            "stats": {
                "total_users": total_users,
                "active_users": active_users,
                "admin_users": admin_users,
                "total_rooms": total_rooms,
                "total_messages": total_messages,
            },
        },
    )


@admin_router.get("/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    List all users; allow toggling active/admin flags.
    """
    res = await db.execute(select(User).order_by(User.id.asc()))
    users: List[User] = res.scalars().all()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "admin": admin,
            "users": users,
        },
    )


@admin_router.post("/users/{user_id}/toggle-active")
async def admin_toggle_user_active(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent locking yourself out
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate yourself",
        )

    user.is_active = not user.is_active
    await db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@admin_router.post("/users/{user_id}/toggle-admin")
async def admin_toggle_user_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent removing your own admin
    if user.id == admin.id and user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin role",
        )

    user.is_admin = not user.is_admin
    await db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
