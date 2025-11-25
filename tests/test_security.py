from datetime import timedelta

import pytest

from app.security import security
from app.core import config


def test_password_hash_and_verify():
    plain = "mysecretpassword"
    hashed = security.hash_password(plain)
    assert hashed != plain
    assert security.verify_password(plain, hashed)
    assert not security.verify_password("wrong", hashed)


def test_jwt_create_and_decode(monkeypatch):
    # Ensure a stable test secret
    monkeypatch.setattr(config.settings, "JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(config.settings, "JWT_ALGORITHM", "HS256")

    token = security.create_jwt_token(subject="123", expires_delta=timedelta(minutes=5), token_type="access")
    assert isinstance(token, str) and token

    payload = security.decode_jwt_token(token)
    assert payload is not None
    assert payload.get("sub") == "123"
    assert payload.get("type") == "access"


def test_jwt_decode_invalid_token(monkeypatch):
    monkeypatch.setattr(config.settings, "JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(config.settings, "JWT_ALGORITHM", "HS256")

    bad = "this.is.not.a.jwt"
    assert security.decode_jwt_token(bad) is None
