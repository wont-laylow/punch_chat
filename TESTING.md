# Test Suite Documentation

## Overview
This document describes the test suite for the Punch Chat application. The test suite covers essential functionality across security, schemas, services, WebSocket management, and auth integration.

## Test Files

### `tests/conftest.py`
**Purpose:** Pytest configuration and shared fixtures.
**Setup:**
- Configures `pytest-asyncio` plugin for async test support
- Provides `suppress_logging` fixture to reduce test output noise

### `tests/test_security.py`
**Purpose:** Unit tests for password hashing and JWT token operations.
**Tests:**
1. `test_password_hash_and_verify()` — Validates password hashing with pbkdf2_sha256
   - Hashed password differs from plain text
   - Hashed password verifies correctly
   - Wrong password fails verification

2. `test_jwt_create_and_decode()` — Tests JWT token creation and decoding
   - Token is created successfully
   - Token payload contains correct subject, type, and expiry
   - Token can be decoded to retrieve original payload

3. `test_jwt_decode_invalid_token()` — Tests invalid token handling
   - Invalid token strings return `None` instead of raising

### `tests/test_schemas.py`
**Purpose:** Unit tests for Pydantic request/response schemas.
**Tests:**
1. `test_user_create_valid()` — Valid user creation payload
2. `test_user_create_password_too_short()` — Password validation enforces minimum length (6 chars)
3. `test_login_request_valid()` — Valid login payload validation
4. `test_token_pair_valid()` — Token response schema validation
5. `test_chat_room_create_direct()` — Direct room creation schema (expects member_ids as List[str])
6. `test_message_create_valid()` — Message creation schema validation

### `tests/test_services.py`
**Purpose:** Unit tests for business logic services with mock async database.
**Key Component:** `MockAsyncSession` — A lightweight mock of `AsyncSession` that simulates DB operations without a real database.
**Tests:**
1. `test_create_room_direct()` — ChatService.create_room() for direct (1-1) rooms
   - Validates room type is DIRECT
   - Validates is_active flag is True

2. `test_create_room_group()` — ChatService.create_room() for group rooms
   - Validates room type is GROUP
   - Validates name is stored correctly

3. `test_save_message()` — ChatService.save_message()
   - Validates message is persisted with correct room_id, sender_id, content
   - Validates created_at timestamp is set

### `tests/test_websocket_manager.py`
**Purpose:** Unit tests for WebSocket connection management.
**Key Component:** `DummyWebSocket` — A mock WebSocket that simulates accept, send_json, and failure scenarios.
**Tests:**
1. `test_connect_and_broadcast_and_disconnect()` — Full WebSocket lifecycle
   - Two clients connect to the same room
   - Broadcast sends message to both clients
   - Disconnect removes clients and cleans up empty rooms

2. `test_broadcast_handles_send_errors()` — Robustness against failed sends
   - One good WebSocket, one that fails on send
   - Broadcast does not raise exception
   - Failed WebSocket is removed from active connections
   - Good WebSocket receives message successfully

### `tests/test_auth_integration.py`
**Purpose:** Integration tests for authentication endpoints.
**Tests:**
1. `test_register_endpoint_happy_path()` — FastAPI TestClient tests for /auth/register
   - Valid registration creates user with email and username
   - Endpoint returns 200 status code

2. `test_password_verification_basic()` — Direct password hashing/verification test
   - Password hashing is reversible via verification
   - Wrong password fails verification

## Running Tests

### Run all tests:
```bash
python -m pytest tests/ -v
```

### Run specific test file:
```bash
python -m pytest tests/test_security.py -v
```

### Run specific test function:
```bash
python -m pytest tests/test_security.py::test_password_hash_and_verify -v
```

### Run with coverage (optional):
```bash
pip install pytest-cov
python -m pytest tests/ --cov=app --cov-report=html
```

## Test Results Summary
**Total Tests:** 16
**Status:** All passing ✓
- test_auth_integration.py: 2 passed
- test_schemas.py: 6 passed
- test_security.py: 3 passed
- test_services.py: 3 passed
- test_websocket_manager.py: 2 passed

## Dependencies
The test suite requires:
- `pytest` — Test framework
- `pytest-asyncio` — Async test support
- `httpx` — FastAPI TestClient dependency

These are already in `requirements.txt`.

## Design Notes

### Mock-Based Testing
- `MockAsyncSession` simulates database behavior without requiring a live PostgreSQL instance
- `DummyWebSocket` mocks the FastAPI WebSocket interface for isolated unit tests
- This allows fast test execution and easy iteration during development

### Async Support
- Tests marked with `@pytest.mark.asyncio` use pytest-asyncio for proper async/await execution
- Fixtures configure asyncio mode to "auto" for seamless integration

### Security Testing
- Password tests use the actual `CryptContext` from the project (pbkdf2_sha256)
- JWT tests mock the settings but use real jose.jwt encoding/decoding
- No secrets are logged during test execution

## Future Enhancements
1. Database fixtures using `sqlalchemy.ext.asyncio` with a test database
2. End-to-end WebSocket tests using `websockets` library
3. Load tests using `locust` for WebSocket broadcast performance
4. Integration tests for `ChatService.get_or_create_direct_room()` subquery logic
5. Admin router and user router endpoint tests
6. AI endpoint tests (openai integration mocking)
