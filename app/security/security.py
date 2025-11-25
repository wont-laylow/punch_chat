from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# pbkdf2_sha256 for hashing
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """
    Hash a plain text password using pbkdf2_sha256.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare plain password to stored hash.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt_token(
    subject: str,
    expires_delta: timedelta,
    token_type: str,
) -> str:
    """
    Create a signed JWT token with subject, expiry, and type.
    """
    expire = datetime.utcnow() + expires_delta
    payload: Dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "type": token_type,
    }
    encoded = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    logger.debug("Created %s token for subject=%s expires=%s", token_type, subject, expire.isoformat())
    return encoded


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT and return its payload if valid, otherwise None.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning("JWT decode error: %s", str(e))
        return None


def create_password_reset_token(user_id: int, expires_delta: timedelta = timedelta(hours=1)) -> str:
    """
    Create a password reset token with expiry (default 1 hour).
    Token type is "password_reset".
    """
    expire = datetime.utcnow() + expires_delta
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "type": "password_reset",
    }
    encoded = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    logger.info("Created password reset token for user=%s expires=%s", user_id, expire.isoformat())
    return encoded


def validate_password_reset_token(token: str) -> Optional[int]:
    """
    Validate a password reset token and return the user_id if valid, else None.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "password_reset":
            logger.warning("Password reset token has wrong type: %s", payload.get("type"))
            return None
        user_id = int(payload.get("sub"))
        logger.debug("Validated password reset token for user=%s", user_id)
        return user_id
    except (JWTError, ValueError, TypeError) as e:
        logger.warning("Password reset token validation failed: %s", str(e))
        return None
