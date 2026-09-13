"""Mapping between activity weather models and API views (M24).

The mapper owns the shape of the stored ``data`` JSON: a list of dicts with
exactly the keys in :meth:`from_snapshot`, one per hour. The view converts a
stored row back to typed points; a malformed stored shape (should be impossible
— only this mapper writes it) raises rather than leaking raw JSON.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.models.activity_weather import ActivityWeather
from app.schemas.views.activity_weather_views import (
    ActivityWeatherView,
    WeatherPointView,
)
from app.weather.client import WeatherHourlyData


class ActivityWeatherMapper:
    """Explicit model <-> view conversion for weather snapshots."""

    @staticmethod
    def from_snapshot(
        activity_id: UUID, lat: float, lon: float, hourly: WeatherHourlyData
    ) -> ActivityWeather:
        """A new snapshot row from a parsed upstream response."""
        points = [
            {
                "time": hour,
                "temperature_c": temperature,
                "apparent_temperature_c": apparent,
                "relative_humidity_pct": humidity,
                "dew_point_c": dew_point,
                "weather_code": code,
            }
            for hour, temperature, apparent, humidity, dew_point, code in zip(
                hourly.time,
                hourly.temperature_c,
                hourly.apparent_temperature_c,
                hourly.relative_humidity_pct,
                hourly.dew_point_c,
                hourly.weather_code,
                strict=True,
            )
        ]
        return ActivityWeather(
            uuid=uuid4(),
            activity_id=activity_id,
            lat=lat,
            lon=lon,
            data=points,
        )

    @staticmethod
    def to_view(snapshot: ActivityWeather) -> ActivityWeatherView:
        """The public view of one snapshot row."""
        if not isinstance(snapshot.data, list):  # schema CHECK guarantees this; belt and braces
            raise ValueError("activity_weather.data is not an array.")
        points = [ActivityWeatherMapper._to_point(entry) for entry in snapshot.data]
        return ActivityWeatherView(
            id=snapshot.uuid,
            lat=snapshot.lat,
            lon=snapshot.lon,
            fetched_at=snapshot.fetched_at,
            points=points,
        )

    @staticmethod
    def _to_point(entry: Any) -> WeatherPointView:
        if not isinstance(entry, dict):
            raise ValueError("activity_weather.data entry is malformed.")
        raw_time = entry.get("time")
        if not isinstance(raw_time, str):
            raise ValueError("activity_weather.data entry has no time.")
        # Upstream hours are UTC wall-clock strings without a suffix; make them aware.
        time = datetime.fromisoformat(raw_time).replace(tzinfo=UTC)

        def number(key: str) -> float | None:
            value = entry.get(key)
            return float(value) if isinstance(value, (int, float)) else None

        code = entry.get("weather_code")
        return WeatherPointView(
            time=time,
            temperature_c=number("temperature_c"),
            apparent_temperature_c=number("apparent_temperature_c"),
            relative_humidity_pct=number("relative_humidity_pct"),
            dew_point_c=number("dew_point_c"),
            weather_code=code if isinstance(code, int) else None,
        )
