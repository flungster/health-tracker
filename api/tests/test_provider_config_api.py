"""Tests for the provider client configuration API (M11c): the
deployment's OAuth client per provider, managed server-level (any
authenticated user), one credential set per provider, secret never
exposed.

    GET    /api/v1/providers/{p}/client/config   -> masked view
    PUT    /api/v1/providers/{p}/client/config   -> upsert (client_secret optional
                                              = keep the existing secret)
    DELETE /api/v1/providers/{p}/client/config   -> soft-delete
    GET    /api/v1/providers              -> ``configured`` from the DB
"""

from fastapi.testclient import TestClient


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _strava_entry(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.get("/api/v1/providers", headers=headers)
    assert response.status_code == 200, response.text
    for entry in response.json()["providers"]:
        if entry["value"] == "strava":
            return entry
    raise AssertionError("strava missing from /providers")


class TestProviderConfigApi:
    def test_unauthenticated_put_is_rejected(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345", "client_secret": "s3cret"},
        )
        assert response.status_code == 401

    def test_configure_then_get_masks_the_secret(self, client: TestClient, register_user) -> None:
        token = str(register_user()["token"])
        headers = _headers(token)

        put = client.put(
            "/api/v1/providers/strava/client/config",
            json={
                "client_id": "12345",
                "client_secret": "s3cret",
                "display_name": "Homelab Strava",
            },
            headers=headers,
        )
        assert put.status_code in (200, 201), put.text

        get = client.get("/api/v1/providers/strava/client/config", headers=headers)
        assert get.status_code == 200, get.text
        body = get.json()
        assert body["configured"] is True
        assert body["client_id"] == "12345"
        assert "s3cret" not in get.text  # the secret is never exposed

    def test_put_without_secret_keeps_existing(self, client: TestClient, register_user) -> None:
        token = str(register_user()["token"])
        headers = _headers(token)

        first = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345", "client_secret": "first-secret"},
            headers=headers,
        )
        assert first.status_code in (200, 201), first.text

        second = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345", "display_name": "Renamed"},
            headers=headers,
        )
        assert second.status_code in (200, 201), second.text

        get = client.get("/api/v1/providers/strava/client/config", headers=headers)
        assert get.status_code == 200, get.text
        assert get.json()["configured"] is True
        assert "first-secret" not in get.text

    def test_delete_disconnects(self, client: TestClient, register_user) -> None:
        token = str(register_user()["token"])
        headers = _headers(token)

        put = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345", "client_secret": "s3cret"},
            headers=headers,
        )
        assert put.status_code in (200, 201), put.text

        delete = client.delete("/api/v1/providers/strava/client/config", headers=headers)
        assert delete.status_code in (200, 204), delete.text

        get = client.get("/api/v1/providers/strava/client/config", headers=headers)
        assert get.status_code == 200, get.text
        assert get.json()["configured"] is False
        assert _strava_entry(client, headers)["configured"] is False

    def test_unknown_provider_is_404(self, client: TestClient, register_user) -> None:
        token = str(register_user()["token"])
        headers = _headers(token)

        # Positive control: a real provider resolves (and is not configured
        # on a fresh database).
        known = client.get("/api/v1/providers/strava/client/config", headers=headers)
        assert known.status_code == 200, known.text
        assert known.json()["configured"] is False

        unknown = client.get(
            "/api/v1/providers/definitely-not-a-provider/client/config", headers=headers
        )
        assert unknown.status_code == 404

    def test_configured_flag_reflects_the_db(self, client: TestClient, register_user) -> None:
        token = str(register_user()["token"])
        headers = _headers(token)

        # Fresh database: not configured (no env involvement in M11c+).
        assert _strava_entry(client, headers)["configured"] is False

        put = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345", "client_secret": "s3cret"},
            headers=headers,
        )
        assert put.status_code in (200, 201), put.text

        assert _strava_entry(client, headers)["configured"] is True

    def test_first_put_without_a_secret_is_422(self, client: TestClient, register_user) -> None:
        headers = _headers(str(register_user()["token"]))
        response = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345"},
            headers=headers,
        )
        assert response.status_code == 422, response.text

    def test_put_with_an_empty_client_id_is_422(self, client: TestClient, register_user) -> None:
        headers = _headers(str(register_user()["token"]))
        for client_id in ("", "   "):
            response = client.put(
                "/api/v1/providers/strava/client/config",
                json={"client_id": client_id, "client_secret": "s3cret"},
                headers=headers,
            )
            assert response.status_code == 422, response.text

    def test_put_with_oversized_fields_is_422(self, client: TestClient, register_user) -> None:
        headers = _headers(str(register_user()["token"]))
        response = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "x" * 129, "client_secret": "s3cret"},
            headers=headers,
        )
        assert response.status_code == 422, response.text

    def test_put_with_an_unknown_provider_is_404(self, client: TestClient, register_user) -> None:
        headers = _headers(str(register_user()["token"]))
        response = client.put(
            "/api/v1/providers/definitely-not-a-provider/client/config",
            json={"client_id": "12345", "client_secret": "s3cret"},
            headers=headers,
        )
        assert response.status_code == 404, response.text

    def test_delete_without_configuration_is_404(self, client: TestClient, register_user) -> None:
        headers = _headers(str(register_user()["token"]))
        response = client.delete("/api/v1/providers/strava/client/config", headers=headers)
        assert response.status_code == 404, response.text

    def test_display_name_null_clears_and_omitted_keeps(
        self, client: TestClient, register_user
    ) -> None:
        headers = _headers(str(register_user()["token"]))

        client.put(
            "/api/v1/providers/strava/client/config",
            json={
                "client_id": "12345",
                "client_secret": "s3cret",
                "display_name": "Homelab Strava",
            },
            headers=headers,
        )
        # Omitted: kept.
        client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345"},
            headers=headers,
        )
        kept = client.get("/api/v1/providers/strava/client/config", headers=headers).json()
        assert kept["display_name"] == "Homelab Strava"
        # Null: cleared.
        client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345", "display_name": None},
            headers=headers,
        )
        cleared = client.get("/api/v1/providers/strava/client/config", headers=headers).json()
        assert cleared["display_name"] is None

    def test_saved_credentials_make_the_provider_connectable(
        self, client: TestClient, register_user
    ) -> None:
        headers = _headers(str(register_user()["token"]))

        put = client.put(
            "/api/v1/providers/strava/client/config",
            json={"client_id": "12345", "client_secret": "s3cret"},
            headers=headers,
        )
        assert put.status_code == 200, put.text

        # The registry was rebuilt in the write path: connect now works with
        # the just-saved client id — no restart involved.
        connect = client.get("/api/v1/providers/strava/connect", headers=headers)
        assert connect.status_code == 200, connect.text
        assert "client_id=12345" in connect.json()["url"]
