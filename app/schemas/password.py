from typing import Annotated
from pydantic import BaseModel, EmailStr, StringConstraints


class PasswordResetRequest(BaseModel):
    """Request to initiate password reset (email only)."""
    email: EmailStr


class PasswordResetTokenValidation(BaseModel):
    """Response when password reset token is valid."""
    user_id: int
    message: str


class PasswordReset(BaseModel):
    """Payload to reset password with a valid reset token."""
    token: str
    new_password: Annotated[str, StringConstraints(min_length=6, max_length=72)]


class PasswordResetSuccess(BaseModel):
    """Response after successful password reset."""
    message: str
