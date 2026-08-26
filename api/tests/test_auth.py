"""Tests for registration, login, and the error envelope."""

from typing import Any

from fastapi.testclient import TestClient

from app.config import get_settings

# The ``register_user`` fixture (a factory) is defined in tests/conftest.py.
# It is typed Any here to keep this file independent of the fixture module.


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_creates_account_and_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "  Alice ",
            "last_name": "Doe",
            "email": "  Alice@Example.COM ",
            "password": "supersecret1",
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()

    user: dict[str, Any] = body["user"]
    assert user["email"] == "alice@example.com"
    assert user["first_name"] == "Alice"
    assert user["last_name"] == "Doe"
    assert user["id"]
    assert user["created_at"]
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 20

    # The issued token must work immediately.
    me = client.get("/api/v1/users/me", headers=_auth_headers(body["token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_register_rejects_duplicate_email_case_insensitively(
    client: TestClient, register_user: Any
) -> None:
    register_user(email="alice@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Impostor",
            "last_name": "Doe",
            "email": "ALICE@example.com",
            "password": "supersecret1",
        },
    )
    assert response.status_code == 409
    body: dict[str, Any] = response.json()
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["details"] == []


def test_register_rejects_weak_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 422
    body: dict[str, Any] = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert len(body["error"]["details"]) > 0


def test_register_rejects_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "not-an-email",
            "password": "supersecret1",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_returns_token_for_valid_credentials(client: TestClient, register_user: Any) -> None:
    register_user(email="bob@example.com", first_name="Bob")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "supersecret1"},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert body["user"]["email"] == "bob@example.com"
    assert isinstance(body["token"], str)

    me = client.get("/api/v1/users/me", headers=_auth_headers(body["token"]))
    assert me.status_code == 200


def test_login_rejects_wrong_password(client: TestClient, register_user: Any) -> None:
    register_user(email="bob@example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    body: dict[str, Any] = response.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_login_rejects_unknown_email_with_same_message(
    client: TestClient, register_user: Any
) -> None:
    register_user(email="bob@example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_error_envelope_shape(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    body: dict[str, Any] = response.json()
    error = body["error"]
    assert set(error.keys()) == {"code", "message", "details"}
    assert isinstance(error["details"], list)


class TestAuthRateLimiting:
    def test_login_is_throttled_per_client_ip(self, client: TestClient, register_user: Any) -> None:
        register_user(email="bob@example.com")
        payload = {"email": "bob@example.com", "password": "wrongpassword"}

        # The first N attempts from this IP reach the app (and fail)...
        for _ in range(get_settings().login_rate_limit_per_minute):
            response = client.post("/api/v1/auth/login", json=payload)
            assert response.status_code == 401

        # ...and the next one is throttled.
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 429
        body: dict[str, Any] = response.json()
        assert body["error"]["code"] == "RATE_LIMITED"
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert int(retry_after) >= 1

    def test_register_is_throttled_per_client_ip(self, client: TestClient) -> None:
        def _payload(attempt: int) -> dict[str, str]:
            return {
                "first_name": "Spam",
                "last_name": "Bot",
                "email": f"bot{attempt}@example.com",
                "password": "supersecret1",
            }

        limit = get_settings().register_rate_limit_per_minute
        for attempt in range(limit):
            response = client.post("/api/v1/auth/register", json=_payload(attempt))
            assert response.status_code == 201, response.text

        response = client.post("/api/v1/auth/register", json=_payload(limit))
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
