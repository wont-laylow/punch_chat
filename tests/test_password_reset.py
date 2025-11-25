"""
Tests for password reset functionality.
"""

import pytest
from datetime import timedelta

from app.security.security import (
    create_password_reset_token,
    validate_password_reset_token,
    create_jwt_token,
)
from app.core import config as core_config


def test_create_password_reset_token(monkeypatch):
    """Test creating a password reset token."""
    monkeypatch.setattr(core_config.settings, "JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(core_config.settings, "JWT_ALGORITHM", "HS256")

    user_id = 42
    token = create_password_reset_token(user_id, expires_delta=timedelta(hours=1))

    assert isinstance(token, str)
    assert token


def test_validate_password_reset_token(monkeypatch):
    """Test validating a valid password reset token."""
    monkeypatch.setattr(core_config.settings, "JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(core_config.settings, "JWT_ALGORITHM", "HS256")

    user_id = 42
    token = create_password_reset_token(user_id, expires_delta=timedelta(hours=1))

    validated_user_id = validate_password_reset_token(token)
    assert validated_user_id == user_id


def test_validate_invalid_password_reset_token(monkeypatch):
    """Test that invalid password reset tokens return None."""
    monkeypatch.setattr(core_config.settings, "JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(core_config.settings, "JWT_ALGORITHM", "HS256")

    invalid_token = "not.a.valid.token"
    result = validate_password_reset_token(invalid_token)

    assert result is None


def test_validate_password_reset_token_wrong_type(monkeypatch):
    """Test that tokens with wrong type are rejected."""
    monkeypatch.setattr(core_config.settings, "JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(core_config.settings, "JWT_ALGORITHM", "HS256")

    # Create an access token (wrong type)
    wrong_token = create_jwt_token(
        subject="42",
        expires_delta=timedelta(hours=1),
        token_type="access",
    )

    result = validate_password_reset_token(wrong_token)
    assert result is None
