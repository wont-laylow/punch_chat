from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.user import UserPublic


class UserRouter:
    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/users",
            tags=["users"],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.get("/search", response_model=List[UserPublic])(self.search_users)

    async def search_users(
        self,
        q: str = Query(..., min_length=1, max_length=50, description="Search by username"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
    ):
        """
        Search for other users by username (case-insensitive).
        Does not return email or sensitive data.
        """
        stmt = (
            select(User)
            .where(User.username.ilike(f"%{q}%"))
            .limit(20)
        )
        res = await db.execute(stmt)
        users = res.scalars().all()

        # Exclude the current user from the results
        users = [u for u in users if u.id != current_user.id]

        return [UserPublic.model_validate(u) for u in users]
