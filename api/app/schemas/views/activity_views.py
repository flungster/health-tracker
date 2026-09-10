"""View schemas for activities.

Views are the only representation of models that leaves the API. Unit-bearing
fields carry unit-neutral names (``distance``, ``elevation_gain``, ...); the
view-level ``units`` flag says which display system their values are in —
metric users get the stored SI value, imperial users get it converted by the
API (see ``app.schemas.units``). Universal values keep their unit in the name:
calories are always kcal, power is always watts.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActivitySummaryView(BaseModel):
    """Compact activity representation for list feeds.

    ``distance`` / ``elevation_gain`` are in the caller's display system (see
    the list-level ``units``).
    """

    id: UUID
    sport_type: str
    name: str
    started_at: datetime
    duration_seconds: int
    moving_seconds: int | None
    distance: float | None
    calories_kcal: float | None
    elevation_gain: float | None
    heart_rate_avg_bpm: int | None
    provider: str | None  # e.g. "strava"; null for file imports


class ActivitiesListView(BaseModel):
    """A page of the activity feed plus pagination metadata.

    ``units`` names the display system all unit-bearing values in this
    response are expressed in ("metric" or "imperial").
    """

    items: list[ActivitySummaryView]
    total: int
    limit: int
    offset: int
    units: str  # "metric" | "imperial" — display system of all unit-bearing values


class ActivityCountView(BaseModel):
    """How many activities fall in the period, overall and per sport type.

    ``by_sport_type`` lists only sports with at least one activity; the keys
    are sport-type value strings (the same vocabulary as ``sport_type``).
    """

    total: int  # always a number (0 for an empty period)
    by_sport_type: dict[str, int]


class DistanceTrendPointView(BaseModel):
    """One bucket of the distance-over-time trend.

    ``start`` is the UTC instant that begins the bucket (a midnight for day
    buckets, a first-of-month 00:00 UTC for month buckets); ``value`` is the
    distance in the caller's display system (the list-level rule — meters when
    metric, miles otherwise). Buckets with no activity are 0.0; an empty list
    means the period has no distance data at all (the card is null then).
    """

    start: datetime
    value: float


class ActivityPeriodSummaryView(BaseModel):
    """Aggregate stats for one user's activities over a period (dashboard).

    ``units`` names the display system all unit-bearing values are expressed
    in (same rules as list/detail views). A metric with no contributing data
    in the period is ``null``, not zero: a strength-only week has
    ``distance: null`` ("no distance recorded" != "zero travelled").
    """

    units: str  # "metric" | "imperial" — display system of all unit-bearing values
    activity_count: ActivityCountView
    moving_seconds_total: int | None  # null when no activity has a moving time
    distance: float | None  # meters when units is metric, miles otherwise
    elevation_gain: float | None  # meters when units is metric, feet otherwise
    calories_kcal: float | None  # universal — never converted
    avg_heart_rate_bpm: int | None  # mean of the per-activity averages, whole bpm
    weight_lifted: float | None  # kg when units is metric, lb otherwise (strength volume)
    distance_trend: list[DistanceTrendPointView]


class SplitView(BaseModel):
    """One per-distance split."""

    split_type: str
    split_index: int
    duration_seconds: int
    pace_seconds: float
    heart_rate_avg_bpm: int | None
    cadence_avg_rpm: int | None


class SplitsView(BaseModel):
    """All splits of an activity."""

    items: list[SplitView]


class HrZoneView(BaseModel):
    """Seconds spent in each heart-rate zone."""

    zone_1_seconds: int
    zone_2_seconds: int
    zone_3_seconds: int
    zone_4_seconds: int
    zone_5_seconds: int


class RunningMetricsView(BaseModel):
    """Running-specific metrics (None when the activity is not a run).

    Pace fields are seconds per display distance unit — km when ``units`` is
    metric, mi when imperial.
    """

    avg_pace_seconds: float | None
    min_pace_seconds: float | None
    max_pace_seconds: float | None


class WalkingMetricsView(BaseModel):
    """Walking-specific metrics (None when the activity is not a walk).

    The pace is computed at view time from the stored moving time and
    distance (no walking row exists in the database); per-kilometre/mile
    variation is available through ``splits``. Like the running paces, it is
    seconds per display distance unit — km when ``units`` is metric, mi when
    imperial.
    """

    avg_pace_seconds: float | None


class CyclingMetricsView(BaseModel):
    """Cycling-specific metrics (None when the activity is not a ride)."""

    power_avg_w: int | None
    power_max_w: int | None


class RowingMetricsView(BaseModel):
    """Rowing-specific metrics (None when the activity is not a row)."""

    stroke_rate_avg_spm: int | None
    stroke_rate_min_spm: int | None
    stroke_rate_max_spm: int | None
    split_500m_seconds: float | None


class StrengthMetricsView(BaseModel):
    """Strength-specific metrics (None when the activity is not strength).

    ``total_weight`` is kg when ``units`` is metric, lb otherwise.
    """

    total_sets: int
    total_exercises: int
    total_weight: float | None


class ActivityDetailView(BaseModel):
    """Full activity representation for the detail page.

    ``units`` names the display system all unit-bearing values in this
    response are expressed in ("metric" or "imperial"). ``splits`` already
    contains only the splits of that system (km rows for metric, mi rows for
    imperial) — both are precomputed at import time.
    """

    id: UUID
    sport_type: str
    name: str
    description: str | None
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    moving_seconds: int | None
    distance: float | None  # meters when units is metric, miles otherwise
    calories_kcal: float | None
    elevation_gain: float | None  # meters when units is metric, feet otherwise
    heart_rate_min_bpm: int | None
    heart_rate_avg_bpm: int | None
    heart_rate_max_bpm: int | None
    cadence_avg_rpm: int | None
    provider: str | None  # e.g. "strava"; null for file imports
    source_format: str | None  # e.g. "gpx"; null when fetched from a provider
    original_filename: str | None  # the uploaded file name; null for provider fetches
    created_at: datetime
    units: str  # "metric" | "imperial" — display system of all unit-bearing values
    splits: list[SplitView]
    heart_rate_zones: HrZoneView | None
    running: RunningMetricsView | None
    walking: WalkingMetricsView | None
    cycling: CyclingMetricsView | None
    rowing: RowingMetricsView | None
    strength: StrengthMetricsView | None


class TrackpointView(BaseModel):
    """One recorded sample of an activity.

    ``altitude`` / ``speed`` are in the caller's display system (m and m/s
    when metric, ft and mph otherwise — see the view-level ``units``).
    """

    seq: int
    recorded_at: datetime | None
    lat: float | None
    lon: float | None
    altitude: float | None
    heart_rate_bpm: int | None
    cadence_rpm: int | None
    speed: float | None
    power_w: int | None


class TrackpointsView(BaseModel):
    """All samples of an activity.

    ``units`` names the display system ``altitude`` / ``speed`` are expressed
    in ("metric" or "imperial"). Positions (lat/lon) never change.
    """

    items: list[TrackpointView]
    units: str  # "metric" | "imperial" — display system of altitude/speed


class SportTypeView(BaseModel):
    """One sport type from the activity_types reference table."""

    value: str
    description: str


class SportsView(BaseModel):
    """The canonical list of sport types (for pickers)."""

    sports: list[SportTypeView]
