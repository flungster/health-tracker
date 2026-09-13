"""Activity weather routes (M24): opt-in, cached per activity."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.http.dependencies import get_activity_weather_service, get_current_user
from app.models.user import User
from app.schemas.views.activity_weather_views import (
    ActivityWeatherView,
)
from app.services.activity_weather_service import (
    ActivityWeatherService,
)

router = APIRouter(prefix="/api/v1", tags=["activities"])


@router.get("/activities/{activity_id}/weather", response_model=ActivityWeatherView)
def get_weather(
    activity_id: UUID,
    weather_service: ActivityWeatherService = Depends(get_activity_weather_service),
    current_user: User = Depends(get_current_user),
) -> ActivityWeatherView:
    """The caller's activity weather, if fetched before (404 when not yet)."""
    return weather_service.get_for_user(current_user.uuid, activity_id)


@router.post("/activities/{activity_id}/weather", response_model=ActivityWeatherView)
def fetch_weather(
    activity_id: UUID,
    weather_service: ActivityWeatherService = Depends(get_activity_weather_service),
    current_user: User = Depends(get_current_user),
) -> ActivityWeatherView:
    """Fetch the caller's activity weather, reusing a cached snapshot when present.

    422 for an activity without GPS; 502 (WEATHER_ERROR) when the upstream
    lookup fails — nothing is stored then, so a retry starts clean. Data:
    Open-Meteo Historical Forecast API (CC BY 4.0, attribution shown in the UI).
    """
    return weather_service.fetch_or_cached(current_user.uuid, activity_id)
