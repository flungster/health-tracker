"""View schemas for cached activity weather (M24).

Times are UTC ISO 8601 instants; the client renders them in the user's
display timezone (M23). Values keep upstream nulls as ``None`` — the UI shows
an em dash for a missing field. Attribution (Open-Meteo, CC BY 4.0) is part
of the UI, not a field here.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WeatherPointView(BaseModel):
    """One hour of the snapshot (parallel to its neighbours in ``points``).

    Temperature fields are unit-bearing: expressed in the caller's display
    system named by ``ActivityWeatherView.units`` (°C for metric, °F for
    imperial), converted at read time from the stored Celsius snapshot (M14b).
    """

    time: datetime  # UTC hour the value applies from, e.g. 2026-09-05T13:00Z
    temperature: float | None  # display units (see above)
    apparent_temperature: float | None  # "feels-like", display units
    relative_humidity_pct: float | None  # unitless percentage
    dew_point: float | None  # display units (see above)
    weather_code: int | None  # WMO code; the UI maps it to a label


class ActivityWeatherView(BaseModel):
    """The cached weather snapshot of one activity."""

    id: UUID  # public uuid (identifier convention)
    lat: float  # the point measured for (the activity's first GPS trackpoint)
    lon: float
    fetched_at: datetime  # when the upstream fetch happened (UTC)
    units: str  # "metric" | "imperial": the system point temperatures are in
    points: list[WeatherPointView]
