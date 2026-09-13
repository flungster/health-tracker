"""Unit tests for the Open-Meteo client (M24a): parsing, null safety, failures."""

from datetime import date
from typing import Any, cast

import httpx
import pytest

from app.errors.app_error import WeatherUpstreamError
from app.weather.client import OpenMeteoClient


def _client(handler: httpx.MockTransport) -> OpenMeteoClient:
    return OpenMeteoClient(base_url="https://weather.test", transport=handler)


def _hourly_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "hourly": {
            "time": ["2026-09-05T13:00", "2026-09-05T14:00"],
            "temperature_2m": [21.3, 22.8],
            "apparent_temperature": [20.9, None],  # a missing value stays null
            "relative_humidity_2m": [54.0, 51.0],
            "dew_point_2m": [11.7, 12.0],
            "weather_code": [2, 3],
        }
    }
    body.update(overrides)
    return body


def test_fetch_hourly_parses_the_series() -> None:
    seen_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = str(request.url)
        return httpx.Response(200, json=_hourly_body())

    client = _client(httpx.MockTransport(handler))
    data = client.fetch_hourly(48.85, 2.35, date(2026, 9, 5), date(2026, 9, 5))

    assert data.time == ["2026-09-05T13:00", "2026-09-05T14:00"]
    assert data.temperature_c == [21.3, 22.8]
    # Upstream nulls are preserved (the view keeps them, the UI shows an em dash).
    assert data.apparent_temperature_c == [20.9, None]
    assert data.weather_code == [2, 3]

    # The request is a plain keyless GET with the UTC-hour contract.
    assert "weather.test/v1/forecast" in seen_url
    for expected in (
        "latitude=48.85000",
        "longitude=2.35000",
        "start_date=2026-09-05",
        "end_date=2026-09-05",
        "timezone=UTC",
    ):
        assert expected in seen_url, f"missing {expected!r} in {seen_url}"


def test_upstream_error_becomes_weather_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": True})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(WeatherUpstreamError) as excinfo:
        client.fetch_hourly(48.85, 2.35, date(2026, 9, 5), date(2026, 9, 5))
    assert "503" in str(excinfo.value)


def test_network_failure_becomes_weather_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(WeatherUpstreamError) as excinfo:
        client.fetch_hourly(48.85, 2.35, date(2026, 9, 5), date(2026, 9, 5))
    assert "Could not reach" in str(excinfo.value)


def test_non_json_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>nope</html>")

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(WeatherUpstreamError):
        client.fetch_hourly(48.85, 2.35, date(2026, 9, 5), date(2026, 9, 5))


@pytest.mark.parametrize(
    ("body", "message_fragment"),
    [
        ({"no_hourly": True}, "missing its hourly data"),  # top-level shape wrong
        ({"hourly": {"time": []}}, "no data for this range"),  # empty series
        ({"hourly": {"time": "not-a-list"}}, "'time' was malformed"),
        (
            {
                "hourly": {
                    **_hourly_body()["hourly"],  # type: ignore[arg-type]
                    "temperature_2m": [1.0],  # length mismatch with time (2 entries)
                }
            },
            "does not match the time series length",
        ),
    ],
)
def test_malformed_bodies_are_rejected(body: dict[str, Any], message_fragment: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(WeatherUpstreamError) as excinfo:
        client.fetch_hourly(48.85, 2.35, date(2026, 9, 5), date(2026, 9, 5))
    assert message_fragment in str(excinfo.value)


def test_null_values_inside_the_series_stay_none() -> None:
    # A present field holding nulls is valid upstream data (a missing value),
    # not a malformed body — the client keeps it as None for the view.

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2026-09-05T13:00"],
                    "temperature_2m": [None],
                    "apparent_temperature": [None],
                    "relative_humidity_2m": [49.0],
                    "dew_point_2m": [None],
                    "weather_code": [1],
                }
            },
        )

    client = _client(httpx.MockTransport(handler))
    data = cast(Any, client.fetch_hourly(48.85, 2.35, date(2026, 9, 5), date(2026, 9, 5)))
    assert data.temperature_c == [None]
    assert data.apparent_temperature_c == [None]
    assert data.relative_humidity_pct == [49.0]
    assert data.weather_code == [1]
