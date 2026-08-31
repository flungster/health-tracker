"""Activity import business logic: parse, compute, persist."""

import logging
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from app.config import Settings
from app.dao.activity_dao import ActivityDao
from app.dao.activity_split_dao import ActivitySplitDao
from app.dao.activity_trackpoint_dao import ActivityTrackpointDao
from app.dao.sport_activity_dao import (
    CyclingActivityDao,
    RowingActivityDao,
    RunningActivityDao,
    StrengthActivityDao,
)
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import ActivityImportError, ValidationError
from app.imports import (
    DEFAULT_SPORT,
    SPORT_TYPES,
    FormatDetector,
    ParsedActivity,
)
from app.models.activity import Activity
from app.providers import Provider
from app.schemas.mappers.activity_mapper import ActivityMapper
from app.services.activity_stats import ActivityStatistics, ActivityStats

logger = logging.getLogger(__name__)

_MAX_EXTENSIONS = {".gpx", ".tcx", ".fit"}
PROVIDER_VALUES: tuple[str, ...] = tuple(member.value for member in Provider)


class ImportService:
    """Imports an uploaded activity file for a user.

    Orchestrates: file-size check, format detection, parsing, statistics,
    original-file storage, and persistence of every derived row.
    """

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        activity_dao: ActivityDao,
        trackpoint_dao: ActivityTrackpointDao,
        split_dao: ActivitySplitDao,
        running_dao: RunningActivityDao,
        cycling_dao: CyclingActivityDao,
        rowing_dao: RowingActivityDao,
        strength_dao: StrengthActivityDao,
        detector: FormatDetector,
        statistics: ActivityStatistics,
        settings: Settings,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._activity_dao = activity_dao
        self._trackpoint_dao = trackpoint_dao
        self._split_dao = split_dao
        self._running_dao = running_dao
        self._cycling_dao = cycling_dao
        self._rowing_dao = rowing_dao
        self._strength_dao = strength_dao
        self._detector = detector
        self._statistics = statistics
        self._settings = settings

    def import_activity(
        self,
        user_id: UUID,
        filename: str,
        data: bytes,
        sport_override: str | None = None,
        name_override: str | None = None,
    ) -> Activity:
        """Import one activity file. Commits on success.

        Raises ValidationError for an oversized file or bad sport override,
        and ActivityImportError when the file cannot be read as an activity.
        """
        settings = self._settings
        max_bytes = settings.max_upload_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise ValidationError(
                f"File exceeds the maximum upload size of {settings.max_upload_mb} MB."
            )
        if sport_override is not None and sport_override not in SPORT_TYPES:
            raise ValidationError(
                f"Unknown sport type {sport_override!r}. Expected one of: {', '.join(SPORT_TYPES)}."
            )

        parser = self._detector.detect(filename, data)
        parsed = parser.parse(data)
        trackpoint_count = len(parsed.trackpoints)
        if trackpoint_count > settings.max_trackpoints:
            raise ActivityImportError(
                f"The file contains {trackpoint_count:,} trackpoints; "
                f"the maximum is {settings.max_trackpoints:,}."
            )
        if parsed.started_at is None:
            raise ActivityImportError("The file contains no timestamp data; cannot import it.")
        for warning in parsed.warnings:
            logger.info("Import warning for %s: %s", filename, warning)

        activity_id = uuid4()
        file_path = self._store_file(user_id, activity_id, filename, data, parser.source_format)

        return self.import_parsed(
            user_id,
            parsed,
            activity_uuid=activity_id,
            source_format=parser.source_format,
            original_filename=filename,
            file_path=file_path,
            name_override=name_override,
            sport_override=sport_override,
        )

    def import_parsed(
        self,
        user_id: UUID,
        parsed: ParsedActivity,
        *,
        activity_uuid: UUID | None = None,
        source_format: str | None = None,
        provider: str | None = None,
        external_activity_id: str | None = None,
        original_filename: str | None = None,
        file_path: str | None = None,
        name_override: str | None = None,
        sport_override: str | None = None,
    ) -> Activity:
        """Persist a parsed activity for a user. Commits on success.

        Shared by file import (``import_activity``) and provider sync: the
        caller supplies the provenance — a file/export ``source_format`` for
        uploads, or a ``provider`` with its ``external_activity_id`` for
        activities fetched from a provider API.

        Raises ValidationError for a bad sport override or provider, and
        ActivityImportError when the activity carries no timestamp data.
        """
        if sport_override is not None and sport_override not in SPORT_TYPES:
            raise ValidationError(
                f"Unknown sport type {sport_override!r}. Expected one of: {', '.join(SPORT_TYPES)}."
            )
        if provider is not None and provider not in PROVIDER_VALUES:
            raise ValidationError(
                f"Unknown provider {provider!r}. Expected one of: {', '.join(PROVIDER_VALUES)}."
            )
        if parsed.started_at is None:
            raise ActivityImportError("The activity contains no timestamp data; cannot import it.")
        for warning in parsed.warnings:
            if original_filename is not None:
                logger.info("Import warning for %s: %s", original_filename, warning)
            else:
                logger.info("Import warning: %s", warning)

        started_at = parsed.started_at
        duration = parsed.duration_seconds
        if duration is None and parsed.ended_at is not None:
            duration = max(0, int((parsed.ended_at - started_at).total_seconds()))
        if duration is None:
            duration = 0
        ended_at = parsed.ended_at or (started_at + timedelta(seconds=duration))

        sport = self._resolve_sport(sport_override, parsed)
        name = (name_override or parsed.name or self._name_fallback(original_filename)).strip()
        if not name:
            name = "Imported activity"

        # Note: heart-rate zones are NOT computed here — they are relative to
        # the viewer's profile max heart rate and are computed at view time.
        stats = self._statistics.compute(parsed)

        if activity_uuid is None:
            activity_uuid = uuid4()

        activity = ActivityMapper.create_activity(
            activity_uuid=activity_uuid,
            user_id=user_id,
            sport_type=sport,
            name=name,
            description=parsed.description,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration,
            moving_seconds=parsed.moving_seconds,
            distance_m=parsed.distance_m,
            calories_kcal=parsed.calories_kcal,
            elevation_gain_m=parsed.elevation_gain_m,
            heart_rate_min_bpm=stats.heart_rate_min_bpm,
            heart_rate_avg_bpm=stats.heart_rate_avg_bpm,
            heart_rate_max_bpm=stats.heart_rate_max_bpm,
            cadence_avg_rpm=stats.cadence_avg_rpm,
            source_format=source_format,
            provider=provider,
            external_activity_id=external_activity_id,
            original_filename=original_filename,
            file_path=file_path,
        )
        self._activity_dao.add(activity)
        self._trackpoint_dao.add_all(
            ActivityMapper.create_trackpoints(activity_uuid, parsed.trackpoints)
        )
        self._split_dao.add_all(ActivityMapper.create_splits(activity_uuid, stats.splits))
        self._add_sport_row(activity, sport, stats)

        self._unit_of_work.commit()
        logger.info(
            "Imported %s activity %s for user %s (%d trackpoints)",
            sport,
            activity.uuid,
            user_id,
            len(parsed.trackpoints),
        )
        return activity

    @staticmethod
    def _name_fallback(original_filename: str | None) -> str:
        """Display-name fallback: the file stem for uploads, a generic label otherwise."""
        if original_filename is not None and Path(original_filename).stem:
            return Path(original_filename).stem
        return "Imported activity"

    def _resolve_sport(self, override: str | None, parsed: ParsedActivity) -> str:
        if override:
            return override
        if parsed.sport_type:
            return parsed.sport_type
        logger.info("File carried no sport information; defaulting to %s", DEFAULT_SPORT)
        return DEFAULT_SPORT

    def _store_file(
        self, user_id: UUID, activity_id: UUID, filename: str, data: bytes, source_format: str
    ) -> str:
        """Persist the original file under uploads/<user_id>/<activity_id><ext>."""
        settings = self._settings
        user_dir = Path(settings.uploads_dir) / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix.lower()
        if suffix not in _MAX_EXTENSIONS:
            suffix = f".{source_format}"
        target = user_dir / f"{activity_id}{suffix}"
        target.write_bytes(data)
        return str(target)

    def _add_sport_row(self, activity: Activity, sport_type: str, stats: ActivityStats) -> None:
        """Insert the sport-specific metric row, when the sport has a table."""
        if sport_type == "running":
            self._running_dao.add(
                ActivityMapper.create_running_activity(
                    activity.uuid,
                    avg_pace_s_per_km=stats.running_avg_pace_s_per_km,
                    min_pace_s_per_km=stats.running_min_pace_s_per_km,
                    max_pace_s_per_km=stats.running_max_pace_s_per_km,
                )
            )
        elif sport_type == "cycling":
            self._cycling_dao.add(
                ActivityMapper.create_cycling_activity(
                    activity.uuid,
                    power_avg_w=stats.cycling_power_avg_w,
                    power_max_w=stats.cycling_power_max_w,
                )
            )
        elif sport_type == "rowing":
            self._rowing_dao.add(
                ActivityMapper.create_rowing_activity(
                    activity.uuid,
                    split_500m_seconds=stats.rowing_split_500m_seconds,
                )
            )
        elif sport_type == "strength":
            self._strength_dao.add(ActivityMapper.create_strength_activity(activity.uuid))
