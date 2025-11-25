from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.schemas.auth import LoginRequest, TokenPair
from app.security.security import (
    hash_password,
    verify_password,
    create_jwt_token,
)
from app.api.deps import get_current_user
from app.core.logger import get_logger

logger = get_logger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/register", response_model=UserRead)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user with email, username, and password.
    """
    logger.info("Register attempt: email=%s username=%s", data.email, data.username)

    existing = await db.execute(
        select(User).where(
            (User.email == data.email)
            | (User.username == data.username)
        )
    )
    if existing.scalars().first() is not None:
        logger.warning("Registration failed: email or username taken: %s / %s", data.email, data.username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already taken",
        )

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("User registered id=%s email=%s username=%s", user.id, user.email, user.username)

    return user


@router.post("/login", response_model=TokenPair)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user and return access + refresh tokens.
    """
    logger.info("Login attempt for email=%s", data.email)

    result = await db.execute(
        select(User).where(User.email == data.email)
    )
    user = result.scalars().first()

    if not user or not verify_password(data.password, user.hashed_password):
        logger.warning("Login failed for email=%s", data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User inactive",
        )

    access_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_jwt_token(
        subject=str(user.id),
        expires_delta=access_expires,
        token_type="access",
    )
    refresh_token = create_jwt_token(
        subject=str(user.id),
        expires_delta=refresh_expires,
        token_type="refresh",
    )

    logger.info("User logged in id=%s email=%s", user.id, user.email)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.
    """
    return current_user
