"""
Integration tests for auth endpoints (requires test database).
Run with: pytest tests/test_auth_integration.py -v
(Requires a test database to be running.)
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.db import get_db
from app.models.user import User
from app.security.security import hash_password


@pytest.fixture
def mock_async_db():
    """Mock async database for testing."""
    class MockDB:
        def __init__(self):
            self.users = {}
            self.counter = 0

        async def execute(self, stmt):
            # Simplified: return self for chaining
            return self

        def scalars(self):
            return self

        def first(self):
            return None

        def add(self, obj):
            if isinstance(obj, User):
                self.counter += 1
                obj.id = self.counter
                obj.is_active = True
                obj.created_at = datetime.utcnow()
                obj.updated_at = datetime.utcnow()
                self.users[obj.id] = obj

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    return MockDB()


def test_register_endpoint_happy_path(mock_async_db):
    """Test successful user registration."""
    client = TestClient(app)

    # Override get_db dependency
    app.dependency_overrides[get_db] = lambda: mock_async_db

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "securepass123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"


def test_password_verification_basic():
    """Test that hashed password can be verified."""
    plain = "testpass123"
    hashed = hash_password(plain)
    from app.security.security import verify_password
    assert verify_password(plain, hashed)
    assert not verify_password("wrongpass", hashed)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

