"""Open-Meteo Historical Forecast API client (keyless, read-only).

One GET returns the hourly timeseries for a point and date range. Every
method either returns decoded, length-checked data or raises
``WeatherUpstreamError`` (network failure / upstream error). The client is a
plain value object: no per-user state, injectable transport for tests.
"""

from dataclasses import dataclass
from datetime import date

import httpx

from app.errors.app_error import WeatherUpstreamError

#: The hourly variables a snapshot carries (order is part of the wire format).
_HOURLY_FIELDS = ",".join(
    [
        "temperature_2m",
        "apparent_temperature",
        "relative_humidity_2m",
        "dew_point_2m",
        "weather_code",
    ]
)

_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class WeatherHourlyData:
    """One hour per entry, parallel lists (all the same length).

    Values keep upstream nulls as ``None`` — a missing field stays missing
    all the way to the view (the renderer shows an em dash).
    """

    time: list[str]  # ISO 8601 UTC hour, e.g. "2026-09-05T13:00"
    temperature_c: list[float | None]
    apparent_temperature_c: list[float | None]
    relative_humidity_pct: list[float | None]
    dew_point_c: list[float | None]
    weather_code: list[int | None]


class OpenMeteoClient:
    """Talks to the Historical Forecast API. Stateless per call."""

    def __init__(
        self,
        base_url: str = "https://historical-forecast-api.open-meteo.com",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            timeout=_TIMEOUT_SECONDS,
            transport=transport,
            headers={"User-Agent": "health-tracker"},
        )

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._http.close()

    def fetch_hourly(
        self, lat: float, lon: float, start_date: date, end_date: date
    ) -> WeatherHourlyData:
        """The hourly series for ``start_date..end_date`` (UTC days, inclusive)."""
        params = {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": _HOURLY_FIELDS,
            # UTC hours: the app stores and renders instants in one zone.
            "timezone": "UTC",
        }
        try:
            response = self._http.get(f"{self._base_url}/v1/forecast", params=params)
        except httpx.TransportError as exc:
            raise WeatherUpstreamError(f"Could not reach the weather service: {exc}.") from exc

        if response.status_code != 200:
            raise WeatherUpstreamError(
                f"Weather service error {response.status_code}. "
                "The weather for this activity could not be fetched."
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise WeatherUpstreamError("Weather service returned non-JSON data.") from exc

        if not isinstance(body, dict):
            raise WeatherUpstreamError("Weather service response was malformed.")

        hourly = body.get("hourly")
        if not isinstance(hourly, dict):
            raise WeatherUpstreamError("Weather service response was missing its hourly data.")

        time = [entry for entry in _as_list(hourly.get("time"), "time") if isinstance(entry, str)]
        if len(time) == 0:
            raise WeatherUpstreamError(
                "Weather service returned no data for this range (history may be missing)."
            )

        temperature_c = _numbers(_as_list(hourly.get("temperature_2m"), "temperature_2m"))
        apparent = _numbers(_as_list(hourly.get("apparent_temperature"), "apparent_temperature"))
        humidity = _numbers(_as_list(hourly.get("relative_humidity_2m"), "relative_humidity_2m"))
        dew_point = _numbers(_as_list(hourly.get("dew_point_2m"), "dew_point_2m"))
        codes = _codes(_as_list(hourly.get("weather_code"), "weather_code"))

        for field, values in (
            ("temperature_2m", temperature_c),
            ("apparent_temperature", apparent),
            ("relative_humidity_2m", humidity),
            ("dew_point_2m", dew_point),
            ("weather_code", codes),
        ):
            if len(values) != len(time):
                raise WeatherUpstreamError(
                    f"Weather service field {field!r} does not match the time series length."
                )

        return WeatherHourlyData(
            time=time,
            temperature_c=temperature_c,
            apparent_temperature_c=apparent,
            relative_humidity_pct=humidity,
            dew_point_c=dew_point,
            weather_code=codes,
        )


def _as_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise WeatherUpstreamError(f"Weather service field {field_name!r} was malformed.")
    return value


def _numbers(values: list[object]) -> list[float | None]:
    """Upstream numbers, keeping nulls as None (a missing value stays missing)."""
    return [float(value) if isinstance(value, (int, float)) else None for value in values]


def _codes(values: list[object]) -> list[int | None]:
    return [value if isinstance(value, int) else None for value in values]
