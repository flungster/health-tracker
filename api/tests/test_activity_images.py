"""Tests for activity image upload, list, serve and delete (M22b)."""

from pathlib import Path
from typing import Any, cast

import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

# Tiny valid magic bytes for the allowed formats (the sniff only checks them).
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"png-payload-bytes"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"jpeg-payload-bytes"
WEBP_BYTES = b"RIFF\x08\x00\x00\x00WEBP" + b"webp-payload-bytes"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Alice",
            "last_name": "Doe",
            "email": email,
            "password": "supersecret1",
        },
    )
    assert response.status_code == 201, response.text
    return cast("dict[str, Any]", response.json())


def _import_activity(client: TestClient, token: str) -> str:
    """Upload the sample GPX and return the new activity's public uuid."""
    gpx = Path(__file__).parent / "fixtures" / "run_sample.gpx"
    response = client.post(
        "/api/v1/activities",
        files={"file": ("run_sample.gpx", gpx.read_bytes(), "application/octet-stream")},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return cast("dict[str, Any]", response.json())["id"]


def _upload(
    client: TestClient,
    activity_id: str,
    headers: dict[str, str] | None = None,
    filename: str = "pic.png",
    data: bytes = PNG_BYTES,
) -> httpx.Response:
    return client.post(
        f"/api/v1/activities/{activity_id}/images",
        files={"file": (filename, data, "application/octet-stream")},
        headers=headers or {},
    )


def test_upload_and_serve_roundtrip(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    user_id = cast("dict[str, Any]", body["user"])["id"]
    activity_id = _import_activity(client, token)

    response = _upload(client, activity_id, headers=_auth(token), filename="holiday.png")
    assert response.status_code == 201, response.text
    image = cast("dict[str, Any]", response.json())

    assert set(image.keys()) == {
        "id",
        "source",
        "original_filename",
        "bytes",
        "created_at",
    }
    assert image["source"] == "uploaded"
    assert image["original_filename"] == "holiday.png"
    assert image["bytes"] == len(PNG_BYTES)

    # The bytes live under uploads/<user_id>/images/ (mirrors the import layout).
    images_dir = uploads_dir / str(user_id) / "images"
    files = list(images_dir.iterdir())
    assert len(files) == 1
    assert files[0].name.startswith(str(image["id"]))
    assert files[0].suffix == ".png"

    # Serving returns the exact bytes with the right media type.
    serve = client.get(
        f"/api/v1/activities/{activity_id}/images/{image['id']}", headers=_auth(token)
    )
    assert serve.status_code == 200, serve.text
    assert serve.headers["content-type"].startswith("image/png")
    assert serve.content == PNG_BYTES


def test_upload_rejects_wrong_extension(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    activity_id = _import_activity(client, cast(str, body["token"]))

    response = _upload(
        client, activity_id, headers=_auth(cast(str, body["token"])), filename="anim.gif"
    )
    assert response.status_code == 422
    error = cast("dict[str, Any]", response.json())["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert "Unsupported image type" in error["message"]


def test_upload_rejects_non_image_bytes(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    activity_id = _import_activity(client, token)

    response = _upload(
        client, activity_id, headers=_auth(token), filename="evil.jpg", data=b"MZ\x90\x00"
    )
    assert response.status_code == 422
    error = cast("dict[str, Any]", response.json())["error"]
    assert "not a valid image" in error["message"]


def test_upload_rejects_empty_file(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    activity_id = _import_activity(client, token)

    response = _upload(client, activity_id, headers=_auth(token), filename="empty.png", data=b"")
    assert response.status_code == 422
    error = cast("dict[str, Any]", response.json())["error"]
    assert "empty" in error["message"].lower()


def test_upload_rejects_oversized_file(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    activity_id = _import_activity(client, token)

    # Keep the fixture's temporary uploads dir (the override replaces it).
    settings = get_settings().model_copy(
        update={"max_upload_mb": 1, "uploads_dir": str(uploads_dir)}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        big = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (2 * 1024 * 1024))
        response = _upload(client, activity_id, headers=_auth(token), filename="big.png", data=big)
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 422
    error = cast("dict[str, Any]", response.json())["error"]
    assert "maximum upload size" in error["message"]


def test_upload_to_someone_elses_activity_is_not_found(
    client: TestClient, uploads_dir: Path
) -> None:
    owner = _register(client, "alice@example.com")
    intruder = _register(client, "bob@example.com")
    activity_id = _import_activity(client, cast(str, owner["token"]))

    response = _upload(client, activity_id, headers=_auth(cast(str, intruder["token"])))

    assert response.status_code == 404
    # Nothing was stored for the intruder.
    assert not (uploads_dir / cast(str, owner["user"]["id"]) / "images").exists()


def test_list_images_in_upload_order(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    activity_id = _import_activity(client, token)

    first = _upload(
        client, activity_id, headers=_auth(token), filename="one.png", data=PNG_BYTES
    ).json()
    second = _upload(
        client, activity_id, headers=_auth(token), filename="two.jpg", data=JPEG_BYTES
    ).json()

    response = client.get(f"/api/v1/activities/{activity_id}/images", headers=_auth(token))
    assert response.status_code == 200, response.text
    items = cast("dict[str, Any]", response.json())["items"]
    assert [item["id"] for item in items] == [first["id"], second["id"]]
    assert [item["bytes"] for item in items] == [len(PNG_BYTES), len(JPEG_BYTES)]


def test_serve_image_via_session_cookie_only(client: TestClient, uploads_dir: Path) -> None:
    """M22a integration: <img> tags authenticate with the cookie, no header."""
    body = _register(client, "alice@example.com")  # sets the cookie in the jar
    token = cast(str, body["token"])
    activity_id = _import_activity(client, token)

    uploaded = cast("dict[str, Any]", _upload(client, activity_id, headers=_auth(token)).json())

    # No Authorization header at all: only the cookie identifies the caller.
    serve = client.get(f"/api/v1/activities/{activity_id}/images/{uploaded['id']}")
    assert serve.status_code == 200, serve.text
    assert serve.content == PNG_BYTES


def test_delete_image_soft_deletes_and_removes_file(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    user_id = cast("dict[str, Any]", body["user"])["id"]
    activity_id = _import_activity(client, token)

    image = cast("dict[str, Any]", _upload(client, activity_id, headers=_auth(token)).json())

    response = client.delete(
        f"/api/v1/activities/{activity_id}/images/{image['id']}", headers=_auth(token)
    )
    assert response.status_code == 204

    # Gone from the list and from disk.
    listing = client.get(f"/api/v1/activities/{activity_id}/images", headers=_auth(token)).json()
    assert cast("dict[str, Any]", listing)["items"] == []

    images_dir = uploads_dir / str(user_id) / "images"
    if images_dir.exists():
        assert not any(images_dir.iterdir())

    # The row survives as a soft delete (history), but is no longer served.
    serve = client.get(
        f"/api/v1/activities/{activity_id}/images/{image['id']}", headers=_auth(token)
    )
    assert serve.status_code == 404


def test_serve_image_of_another_activity_is_not_found(
    client: TestClient, uploads_dir: Path
) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    first_activity = _import_activity(client, token)
    second_activity = _import_activity(client, token)

    image = cast("dict[str, Any]", _upload(client, first_activity, headers=_auth(token)).json())

    response = client.get(
        f"/api/v1/activities/{second_activity}/images/{image['id']}", headers=_auth(token)
    )
    assert response.status_code == 404


def test_serve_missing_file_is_not_found(client: TestClient, uploads_dir: Path) -> None:
    body = _register(client, "alice@example.com")
    token = cast(str, body["token"])
    user_id = cast("dict[str, Any]", body["user"])["id"]
    activity_id = _import_activity(client, token)

    image = cast("dict[str, Any]", _upload(client, activity_id, headers=_auth(token)).json())

    # Simulate disk corruption: the row is fine, the bytes are gone.
    for path in (uploads_dir / str(user_id) / "images").iterdir():
        path.unlink()

    response = client.get(
        f"/api/v1/activities/{activity_id}/images/{image['id']}", headers=_auth(token)
    )
    assert response.status_code == 404
