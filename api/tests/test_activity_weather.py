"""API tests for opt-in activity weather (M24a): fetch-or-cache, cache reuse.

The Open-Meteo client is overridden with a fake (no network in tests); the
client's own parsing/failure behaviour lives in test_weather_client.py.
"""

from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.http.dependencies import get_open_meteo_client
from app.main import app
from app.weather.client import WeatherHourlyData


class FakeWeatherClient:
    """Stands in for OpenMeteoClient; counts how often it was actually called."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_args: tuple[float, float, date, date] | None = None

    def fetch_hourly(
        self, lat: float, lon: float, start_date: date, end_date: date
    ) -> WeatherHourlyData:
        self.calls += 1
        self.last_args = (lat, lon, start_date, end_date)
        base_time = "2026-09-11T08:00"
        return WeatherHourlyData(
            time=[base_time, f"{datetime_add(base_time, 1)}"],
            temperature_c=[20.5, 21.8],
            apparent_temperature_c=[19.7, None],
            relative_humidity_pct=[55.0, 52.0],
            dew_point_c=[11.2, None],
            weather_code=[3, 61],
        )


def datetime_add(iso_hour: str, hours: int) -> str:
    """'2026-09-11T08:00' + hours, in the same naive UTC-hour shape."""
    parts = iso_hour.split(":")
    hour = int(parts[0].split("T")[1]) + hours  # the fixture stays within one day
    return f"{iso_hour.split('T')[0]}T{hour:02d}:00"


@pytest.fixture
def fake_weather():
    """Override the Open-Meteo client dependency with a counting fake."""
    fake = FakeWeatherClient()

    def override():
        return fake

    app.dependency_overrides[get_open_meteo_client] = override
    yield fake
    app.dependency_overrides.pop(get_open_meteo_client, None)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> tuple[str, Any]:
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
    body = cast("dict[str, Any]", response.json())
    return cast(str, body["token"]), cast("dict[str, Any]", body["user"])


def _import(client: TestClient, token: str, filename: str = "run_sample.gpx") -> str:
    """Upload a fixture and return the new activity's public uuid."""
    data = (Path(__file__).parent / "fixtures" / filename).read_bytes()
    response = client.post(
        "/api/v1/activities",
        files={"file": (filename, data, "application/octet-stream")},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return cast("dict[str, Any]", response.json())["id"]


def test_get_before_fetch_is_404(client: TestClient, uploads_dir: Path) -> None:
    token, _ = _register(client, "weather-get@example.com")
    activity_id = _import(client, token)

    response = client.get(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token))
    assert response.status_code == 404, response.text
    error = cast("dict[str, Any]", response.json())["error"]
    assert error["code"] == "NOT_FOUND"


def test_fetch_stores_the_snapshot_and_reuses_it(
    client: TestClient, uploads_dir: Path, fake_weather: FakeWeatherClient
) -> None:
    token, _ = _register(client, "weather-fetch@example.com")
    activity_id = _import(client, token)

    response = client.post(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token))
    assert response.status_code == 200, response.text
    view = cast("dict[str, Any]", response.json())

    assert set(view.keys()) == {"id", "lat", "lon", "fetched_at", "points"}
    # The snapshot is measured for the activity's first GPS trackpoint.
    assert view["lat"] == 48.85
    assert view["lon"] == 2.35
    points = cast("list[dict[str, Any]]", view["points"])
    assert len(points) == 2
    first = points[0]
    assert set(first.keys()) == {
        "time",
        "temperature_c",
        "apparent_temperature_c",
        "relative_humidity_pct",
        "dew_point_c",
        "weather_code",
    }
    assert first["time"] == "2026-09-11T08:00:00Z"
    assert first["temperature_c"] == 20.5
    # Upstream nulls survive the round trip (the UI shows an em dash).
    assert points[1]["apparent_temperature_c"] is None

    # The fetch asked for the activity's UTC day range.
    assert fake_weather.calls == 1
    args = cast(tuple[float, float, date, date], fake_weather.last_args)
    assert (args[0], args[1]) == pytest.approx((48.85, 2.35))

    # Re-POST and GET both serve the cache: no further upstream calls.
    again = client.post(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token))
    assert again.status_code == 200, again.text
    got = client.get(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token))
    assert got.status_code == 200, got.text

    again_view = cast("dict[str, Any]", again.json())
    assert again_view["id"] == view["id"]  # same row, not a re-fetch
    assert cast("dict[str, Any]", got.json())["id"] == view["id"]
    assert fake_weather.calls == 1


def test_no_gps_activity_cannot_be_weathered(
    client: TestClient, uploads_dir: Path, fake_weather: FakeWeatherClient
) -> None:
    token, _ = _register(client, "weather-nogps@example.com")
    # The rower fixture is an indoor session: trackpoints without coordinates.
    activity_id = _import(client, token, "rower_sample.tcx")

    response = client.post(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token))
    assert response.status_code == 422, response.text
    error = cast("dict[str, Any]", response.json())["error"]
    assert error["code"] == "VALIDATION_ERROR"

    # Nothing was fetched, nothing cached.
    assert fake_weather.calls == 0
    got = client.get(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token))
    assert got.status_code == 404, got.text


def test_someone_elses_activity_is_invisible(
    client: TestClient, uploads_dir: Path, fake_weather: FakeWeatherClient
) -> None:
    token_a, _ = _register(client, "weather-owner@example.com")
    activity_id = _import(client, token_a)

    client.post(
        f"/api/v1/activities/{activity_id}/weather", headers=_auth(token_a)
    )  # owner's fetch succeeds and caches

    token_b, _ = _register(client, "weather-stranger@example.com")
    got = client.get(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token_b))
    posted = client.post(f"/api/v1/activities/{activity_id}/weather", headers=_auth(token_b))

    assert got.status_code == 404, got.text  # reads as missing
    assert posted.status_code == 404, posted.text


def test_unauthenticated_is_rejected(client: TestClient) -> None:
    # A well-formed (but unknown) uuid, so the request reaches auth validation.
    response = client.get("/api/v1/activities/00000000-0000-0000-0000-000000000000/weather")
    assert response.status_code == 401, response.text
