"""View schemas for activities.

Views are the only representation of models that leaves the API.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActivitySummaryView(BaseModel):
    """Compact activity representation for list feeds."""

    id: UUID
    sport_type: str
    name: str
    started_at: datetime
    duration_seconds: int
    moving_seconds: int | None
    distance_m: float | None
    calories_kcal: float | None
    elevation_gain_m: float | None
    heart_rate_avg_bpm: int | None


class ActivitiesListView(BaseModel):
    """A page of the activity feed plus pagination metadata."""

    items: list[ActivitySummaryView]
    total: int
    limit: int
    offset: int


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
    """Running-specific metrics (None when the activity is not a run)."""

    avg_pace_s_per_km: float | None
    min_pace_s_per_km: float | None
    max_pace_s_per_km: float | None


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
    """Strength-specific metrics (None when the activity is not strength)."""

    total_sets: int
    total_exercises: int
    total_weight_kg: float | None


class ActivityDetailView(BaseModel):
    """Full activity representation for the detail page."""

    id: UUID
    sport_type: str
    name: str
    description: str | None
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    moving_seconds: int | None
    distance_m: float | None
    calories_kcal: float | None
    elevation_gain_m: float | None
    heart_rate_min_bpm: int | None
    heart_rate_avg_bpm: int | None
    heart_rate_max_bpm: int | None
    cadence_avg_rpm: int | None
    source_format: str
    original_filename: str | None
    created_at: datetime
    splits: list[SplitView]
    heart_rate_zones: HrZoneView | None
    running: RunningMetricsView | None
    cycling: CyclingMetricsView | None
    rowing: RowingMetricsView | None
    strength: StrengthMetricsView | None


class TrackpointView(BaseModel):
    """One recorded sample of an activity."""

    seq: int
    recorded_at: datetime | None
    lat: float | None
    lon: float | None
    altitude_m: float | None
    heart_rate_bpm: int | None
    cadence_rpm: int | None
    speed_mps: float | None
    power_w: int | None


class TrackpointsView(BaseModel):
    """All samples of an activity."""

    items: list[TrackpointView]


class SportsView(BaseModel):
    """The canonical list of sport types (for pickers)."""

    sports: list[str]
