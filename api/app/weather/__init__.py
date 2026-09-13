"""Open-Meteo integration for opt-in activity weather (M24).

One module, one client: the Historical Forecast API is a plain keyless GET
that returns an hourly JSON timeseries. No per-user state, no OAuth — the
"provider rules" about user accounts do not apply; this is a read-only data
source the user explicitly asks to consult (CC BY 4.0 attribution shown in
the UI and docs).
"""

from app.weather.client import OpenMeteoClient, WeatherHourlyData

__all__ = ["OpenMeteoClient", "WeatherHourlyData"]
