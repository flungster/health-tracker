"""Format-neutral activity data produced by the import parsers.

Parsers turn raw file bytes (GPX/TCX/FIT) into these plain dataclasses so the
rest of the application never depends on a specific file format.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ParsedTrackpoint:
    """One recorded sample along the activity (GPS position + physiology)."""

    recorded_at: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    altitude_m: float | None = None
    heart_rate_bpm: int | None = None
    cadence_rpm: int | None = None
    speed_mps: float | None = None
    power_w: int | None = None


@dataclass
class ParsedSportMetrics:
    """Extra metrics that only some sports record (power, stroke rate)."""

    power_avg_w: int | None = None
    power_max_w: int | None = None
    stroke_rate_avg_spm: int | None = None
    stroke_rate_min_spm: int | None = None
    stroke_rate_max_spm: int | None = None


@dataclass
class ParsedActivity:
    """A fully parsed activity, independent of the source file format.

    ``sport_type`` is ``None`` when the file carries no sport information at
    all; the import service applies the default in that case. Missing data
    stays ``None`` and is described in ``warnings``.
    """

    sport_type: str | None = None
    name: str | None = None
    description: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    moving_seconds: int | None = None
    distance_m: float | None = None
    calories_kcal: float | None = None
    elevation_gain_m: float | None = None
    heart_rate_min_bpm: int | None = None
    heart_rate_avg_bpm: int | None = None
    heart_rate_max_bpm: int | None = None
    cadence_avg_rpm: int | None = None
    trackpoints: list[ParsedTrackpoint] = field(default_factory=list)
    sport_metrics: ParsedSportMetrics = field(default_factory=ParsedSportMetrics)
    warnings: list[str] = field(default_factory=list)
