"""Tests for the /users/me endpoints (account and profile updates)."""

from typing import Any

from fastapi.testclient import TestClient

# The ``register_user`` fixture (a factory) is defined in tests/conftest.py.
# It is typed Any here to keep this file independent of the fixture module.


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_get_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_get_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me", headers=_auth_headers("not.a.jwt"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_get_me_returns_own_account(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user(email="carol@example.com", first_name="Carol")
    response = client.get("/api/v1/users/me", headers=_auth_headers(body["token"]))
    assert response.status_code == 200
    user = response.json()
    assert user["email"] == "carol@example.com"
    assert user["first_name"] == "Carol"


def test_update_me_names_and_email(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user(email="carol@example.com")
    headers = _auth_headers(body["token"])

    response = client.patch(
        "/api/v1/users/me",
        json={"first_name": "Caroline", "email": "  New@Example.com "},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    user = response.json()
    assert user["first_name"] == "Caroline"
    assert user["email"] == "new@example.com"

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.json()["first_name"] == "Caroline"
    assert me.json()["email"] == "new@example.com"


def test_update_me_rejects_email_taken_by_other_user(
    client: TestClient, register_user: Any
) -> None:
    register_user(email="carol@example.com")
    second: dict[str, Any] = register_user(email="dave@example.com")

    response = client.patch(
        "/api/v1/users/me",
        json={"email": "carol@example.com"},
        headers=_auth_headers(second["token"]),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_update_me_keeps_unset_fields(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user(
        email="carol@example.com", first_name="Carol", last_name="Doe"
    )
    response = client.patch(
        "/api/v1/users/me",
        json={"first_name": "Caro"},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 200
    user = response.json()
    assert user["first_name"] == "Caro"
    assert user["last_name"] == "Doe"  # untouched
    assert user["email"] == "carol@example.com"  # untouched


def test_change_password(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user(email="carol@example.com")
    headers = _auth_headers(body["token"])

    response = client.patch(
        "/api/v1/users/me",
        json={"current_password": "supersecret1", "new_password": "brandnewpass2"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    # Old password no longer works...
    old = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "supersecret1"},
    )
    assert old.status_code == 401

    # ...new password does.
    new = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "brandnewpass2"},
    )
    assert new.status_code == 200


def test_change_password_rejects_wrong_current_password(
    client: TestClient, register_user: Any
) -> None:
    body: dict[str, Any] = register_user(email="carol@example.com")
    response = client.patch(
        "/api/v1/users/me",
        json={"current_password": "nope", "new_password": "brandnewpass2"},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_profile_is_empty_initially(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    response = client.get("/api/v1/users/me/profile", headers=_auth_headers(body["token"]))
    assert response.status_code == 200
    assert response.json() == {
        "max_heart_rate": None,
        "resting_heart_rate": None,
    }


def test_profile_update_and_read(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    headers = _auth_headers(body["token"])

    first = client.patch(
        "/api/v1/users/me/profile",
        json={"max_heart_rate": 190},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert first.json() == {"max_heart_rate": 190, "resting_heart_rate": None}

    second = client.patch(
        "/api/v1/users/me/profile",
        json={"resting_heart_rate": 60},
        headers=headers,
    )
    assert second.status_code == 200
    # The earlier value is preserved.
    assert second.json() == {"max_heart_rate": 190, "resting_heart_rate": 60}

    read = client.get("/api/v1/users/me/profile", headers=headers)
    assert read.json() == {"max_heart_rate": 190, "resting_heart_rate": 60}


def test_profile_rejects_out_of_range_values(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    response = client.patch(
        "/api/v1/users/me/profile",
        json={"max_heart_rate": 999},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
