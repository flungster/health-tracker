"""Business logic for opt-in activity weather (M24).

Weather is strictly on-demand: nothing fetches at import time, and a page
re-open never re-fetches — the first successful lookup is cached in
``activity_weather`` and served from there. The snapshot covers the activity's
first GPS trackpoint; activities without GPS cannot be weathered (422).

A failed upstream lookup leaves no row behind: the user can simply try again.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from app.dao.activity_dao import ActivityDao
from app.dao.activity_trackpoint_dao import ActivityTrackpointDao
from app.dao.activity_weather_dao import ActivityWeatherDao
from app.dao.user_profile_dao import UserProfileDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError, ValidationError
from app.models.activity import Activity
from app.schemas.mappers.activity_weather_mapper import (
    ActivityWeatherMapper,
)
from app.schemas.units import UnitSystem, units_for
from app.schemas.views.activity_weather_views import (
    ActivityWeatherView,
)
from app.weather.client import OpenMeteoClient


class ActivityWeatherService:
    """Fetch-once, cache-forever weather for the caller's own activities."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        weather_dao: ActivityWeatherDao,
        activity_dao: ActivityDao,
        trackpoint_dao: ActivityTrackpointDao,
        profile_dao: UserProfileDao,
        client: OpenMeteoClient,
    ) -> None:
        self._uow = unit_of_work
        self._weather_dao = weather_dao
        self._activity_dao = activity_dao
        self._trackpoint_dao = trackpoint_dao
        self._profile_dao = profile_dao
        self._client = client

    def get_for_user(self, user_id: UUID, activity_uuid: UUID) -> ActivityWeatherView:
        """The cached snapshot of the caller's activity (404 when not fetched yet)."""
        self._require_activity(user_id, activity_uuid)
        snapshot = self._weather_dao.get_live_for_activity(activity_uuid)
        if snapshot is None:
            raise NotFoundError("Weather has not been fetched for this activity yet.")
        return ActivityWeatherMapper.to_view(snapshot, self._units_for(user_id))

    def fetch_or_cached(self, user_id: UUID, activity_uuid: UUID) -> ActivityWeatherView:
        """The snapshot of the caller's activity, fetching it on first use.

        Reuses a live row when present (no upstream call); otherwise resolves
        the activity's first GPS point, asks Open-Meteo for the UTC day range
        covering ``started_at..ended_at`` and stores the result. Raises 422 for
        a no-GPS activity, 502 when the upstream lookup fails (nothing stored).
        """
        activity = self._require_activity(user_id, activity_uuid)

        cached = self._weather_dao.get_live_for_activity(activity.uuid)
        if cached is not None:
            return ActivityWeatherMapper.to_view(cached, self._units_for(user_id))

        point = self._trackpoint_dao.first_geographic_point(activity.uuid)
        if point is None:
            raise ValidationError(
                "This activity has no GPS points, so its weather cannot be looked up."
            )

        hourly = self._client.fetch_hourly(
            point[0],
            point[1],
            self._utc_day(activity.started_at),
            self._utc_day(activity.ended_at),
        )

        snapshot = ActivityWeatherMapper.from_snapshot(activity.uuid, point[0], point[1], hourly)
        self._weather_dao.add(snapshot)
        try:
            self._uow.commit()
        except Exception:
            # The upstream call already succeeded; a storage failure rolls back
            # the row (nothing durable), so retrying fetches again — correct.
            self._uow.rollback()
            raise
        return ActivityWeatherMapper.to_view(snapshot, self._units_for(user_id))

    @staticmethod
    def _utc_day(moment: datetime) -> date:
        """The UTC calendar day of an instant (the API's stored-time unit)."""
        return moment.astimezone(UTC).date()

    def _units_for(self, user_id: UUID) -> UnitSystem:
        """The caller's display unit system (metric when there is no profile)."""
        profile = self._profile_dao.get(user_id)
        return units_for(profile.imperial_units_enabled_at if profile is not None else None)

    def _require_activity(self, user_id: UUID, activity_uuid: UUID) -> Activity:
        """The caller's own activity or a 404 (someone else's reads as missing)."""
        activity = self._activity_dao.get_by_uuid(activity_uuid)
        if activity is None or activity.user_id != user_id:
            raise NotFoundError("Activity not found.")
        return activity
