from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.config import settings
from app.core.logger import get_logger
from app.models.user import User
from app.schemas.password import (
    PasswordResetRequest,
    PasswordReset,
    PasswordResetSuccess,
    PasswordResetTokenValidation,
)
from app.security.security import (
    create_password_reset_token,
    validate_password_reset_token,
    hash_password,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/auth/password",
    tags=["password-reset"],
)


@router.post("/reset-request", response_model=dict)
async def request_password_reset(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset. Returns a reset token for the frontend.
    In production, you would email this token to the user instead.
    """
    res = await db.execute(select(User).where(User.email == data.email))
    user = res.scalars().first()

    if not user:
        # Don't reveal whether email exists (security best practice)
        logger.info("Password reset requested for non-existent email=%s", data.email)
        return {
            "message": "If an account exists with that email, a reset link has been sent."
        }

    reset_token = create_password_reset_token(
        user_id=user.id,
        expires_delta=timedelta(hours=1),
    )

    logger.info("Password reset token generated for user=%s (email=%s)", user.id, user.email)

    return {
        "message": "Password reset token generated",
        "token": reset_token,
        "expires_in_hours": 1,
    }


@router.post("/validate-token", response_model=PasswordResetTokenValidation)
async def validate_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate a password reset token and return the associated user_id.
    """
    user_id = validate_password_reset_token(token)

    if not user_id:
        logger.warning("Invalid password reset token provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()

    if not user or not user.is_active:
        logger.warning("Token valid but user inactive: user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not active",
        )

    return PasswordResetTokenValidation(
        user_id=user.id,
        message="Token is valid",
    )


@router.post("/reset", response_model=PasswordResetSuccess)
async def reset_password(
    data: PasswordReset,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset a user's password using a valid reset token.
    """
    user_id = validate_password_reset_token(data.token)

    if not user_id:
        logger.warning("Password reset attempted with invalid token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()

    if not user or not user.is_active:
        logger.warning("Password reset attempted for inactive user: user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not active",
        )

    user.hashed_password = hash_password(data.new_password)
    await db.commit()

    logger.info("Password reset successful for user=%s (email=%s)", user.id, user.email)

    return PasswordResetSuccess(
        message="Password has been reset successfully. Please log in with your new password."
    )
