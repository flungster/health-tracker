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


EMPTY_PROFILE: dict[str, Any] = {
    "max_heart_rate": None,
    "resting_heart_rate": None,
    "date_of_birth": None,
    "custom_zone_1_top_bpm": None,
    "custom_zone_2_top_bpm": None,
    "custom_zone_3_top_bpm": None,
    "custom_zone_4_top_bpm": None,
    "zone_source": None,
    "effective_max_heart_rate": None,
    "age": None,
}


def _view(**overrides: Any) -> dict[str, Any]:
    """A full ProfileView with the given fields overridden."""
    view = dict(EMPTY_PROFILE)
    view.update(overrides)
    return view


def test_profile_is_empty_initially(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    response = client.get("/api/v1/users/me/profile", headers=_auth_headers(body["token"]))
    assert response.status_code == 200
    assert response.json() == EMPTY_PROFILE


def test_profile_update_and_read(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    headers = _auth_headers(body["token"])

    first = client.patch("/api/v1/users/me/profile", json={"max_heart_rate": 190}, headers=headers)
    assert first.status_code == 200, first.text
    # A manual max HR is the active zone reference.
    assert first.json() == _view(
        max_heart_rate=190, zone_source="max_heart_rate", effective_max_heart_rate=190
    )

    second = client.patch(
        "/api/v1/users/me/profile", json={"resting_heart_rate": 60}, headers=headers
    )
    assert second.status_code == 200
    # The earlier value is preserved; resting HR does not affect the zone source.
    assert second.json() == _view(
        max_heart_rate=190,
        resting_heart_rate=60,
        zone_source="max_heart_rate",
        effective_max_heart_rate=190,
    )

    read = client.get("/api/v1/users/me/profile", headers=headers)
    assert read.json() == _view(
        max_heart_rate=190,
        resting_heart_rate=60,
        zone_source="max_heart_rate",
        effective_max_heart_rate=190,
    )


def test_profile_rejects_out_of_range_values(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    response = client.patch(
        "/api/v1/users/me/profile",
        json={"max_heart_rate": 999},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_profile_date_of_birth_sets_age_source(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    response = client.patch(
        "/api/v1/users/me/profile",
        json={"date_of_birth": "1984-05-01"},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["zone_source"] == "age"
    # The age-derived max HR is a plausible int; exact 220-age math is unit-tested.
    assert isinstance(view["effective_max_heart_rate"], int)
    assert 100 <= view["effective_max_heart_rate"] <= 219
    assert isinstance(view["age"], int)
    assert view["age"] > 0


def test_profile_precedence_max_hr_over_age(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    headers = _auth_headers(body["token"])

    client.patch("/api/v1/users/me/profile", json={"date_of_birth": "1984-05-01"}, headers=headers)
    view = client.patch(
        "/api/v1/users/me/profile", json={"max_heart_rate": 185}, headers=headers
    ).json()
    # Both set -> the manual max HR wins.
    assert view["zone_source"] == "max_heart_rate"
    assert view["effective_max_heart_rate"] == 185


def test_profile_precedence_custom_over_max_hr(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    headers = _auth_headers(body["token"])

    client.patch("/api/v1/users/me/profile", json={"max_heart_rate": 185}, headers=headers)
    custom = {
        "custom_zone_1_top_bpm": 120,
        "custom_zone_2_top_bpm": 140,
        "custom_zone_3_top_bpm": 160,
        "custom_zone_4_top_bpm": 178,
    }
    view = client.patch("/api/v1/users/me/profile", json=custom, headers=headers).json()
    # Custom zones beat the manual max HR; no single max HR applies.
    assert view["zone_source"] == "custom"
    assert view["effective_max_heart_rate"] is None

    # Clearing the custom set (all four null) falls back to the max HR.
    cleared = client.patch(
        "/api/v1/users/me/profile", json=dict.fromkeys(custom), headers=headers
    ).json()
    assert cleared["zone_source"] == "max_heart_rate"


def test_profile_null_clears_max_hr(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    headers = _auth_headers(body["token"])

    client.patch("/api/v1/users/me/profile", json={"max_heart_rate": 190}, headers=headers)
    view = client.patch(
        "/api/v1/users/me/profile", json={"max_heart_rate": None}, headers=headers
    ).json()
    assert view["max_heart_rate"] is None
    assert view["zone_source"] is None


def test_profile_omitted_field_kept(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    headers = _auth_headers(body["token"])

    client.patch("/api/v1/users/me/profile", json={"date_of_birth": "1984-05-01"}, headers=headers)
    # Updating only the max HR leaves date_of_birth untouched.
    view = client.patch(
        "/api/v1/users/me/profile", json={"max_heart_rate": 185}, headers=headers
    ).json()
    assert view["date_of_birth"] == "1984-05-01"
    assert view["max_heart_rate"] == 185


def test_profile_rejects_future_date_of_birth(client: TestClient, register_user: Any) -> None:
    from datetime import date, timedelta

    body: dict[str, Any] = register_user()
    future = (date.today() + timedelta(days=1)).isoformat()
    response = client.patch(
        "/api/v1/users/me/profile",
        json={"date_of_birth": future},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 422


def test_profile_rejects_implausible_date_of_birth(client: TestClient, register_user: Any) -> None:
    from datetime import date

    body: dict[str, Any] = register_user()
    # ~176 years old -> beyond the 120 cap.
    response = client.patch(
        "/api/v1/users/me/profile",
        json={"date_of_birth": "1850-01-01"},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 422

    # Born today -> age 0, below the minimum of 1.
    newborn = date.today().isoformat()
    response2 = client.patch(
        "/api/v1/users/me/profile",
        json={"date_of_birth": newborn},
        headers=_auth_headers(body["token"]),
    )
    assert response2.status_code == 422


def test_profile_rejects_partial_custom_zones(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    response = client.patch(
        "/api/v1/users/me/profile",
        json={"custom_zone_1_top_bpm": 120, "custom_zone_2_top_bpm": 140},
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 422


def test_profile_rejects_non_ascending_custom_zones(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    response = client.patch(
        "/api/v1/users/me/profile",
        json={
            "custom_zone_1_top_bpm": 160,
            "custom_zone_2_top_bpm": 140,  # not ascending vs zone 1
            "custom_zone_3_top_bpm": 150,
            "custom_zone_4_top_bpm": 178,
        },
        headers=_auth_headers(body["token"]),
    )
    assert response.status_code == 422


def test_profile_custom_zones_round_trip(client: TestClient, register_user: Any) -> None:
    body: dict[str, Any] = register_user()
    headers = _auth_headers(body["token"])

    custom = {120, 140, 160, 178}
    response = client.patch(
        "/api/v1/users/me/profile",
        json={
            "custom_zone_1_top_bpm": 120,
            "custom_zone_2_top_bpm": 140,
            "custom_zone_3_top_bpm": 160,
            "custom_zone_4_top_bpm": 178,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["zone_source"] == "custom"
    read_back = {view[f"custom_zone_{i}_top_bpm"] for i in range(1, 5)}
    assert read_back == custom
