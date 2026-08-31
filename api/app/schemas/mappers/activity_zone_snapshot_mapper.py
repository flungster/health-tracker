"""Mapping for per-activity heart-rate zone snapshots."""

from uuid import UUID

from app.models.activity_zone_snapshot import ActivityZoneSnapshot
from app.services.activity_stats import HrZoneStats
from app.services.zone_reference import ZoneReference, ZoneSource


class ActivityZoneSnapshotMapper:
    """Translates a zone computation into its stored snapshot and back."""

    @staticmethod
    def create(
        activity_id: UUID, reference: ZoneReference, stats: HrZoneStats
    ) -> ActivityZoneSnapshot:
        """A new snapshot recording the reference ``stats`` were computed from.

        Only the fields matching ``reference.source`` are populated; the rest
        stay NULL so a row always says exactly what it was computed from.
        """
        tops = reference.custom_zone_tops if reference.source is ZoneSource.CUSTOM else None
        return ActivityZoneSnapshot(
            activity_id=activity_id,
            source=reference.source.value,
            max_heart_rate=None if tops is not None else reference.max_heart_rate,
            age=reference.age,
            custom_zone_1_top_bpm=tops[0] if tops is not None else None,
            custom_zone_2_top_bpm=tops[1] if tops is not None else None,
            custom_zone_3_top_bpm=tops[2] if tops is not None else None,
            custom_zone_4_top_bpm=tops[3] if tops is not None else None,
            zone_1_seconds=stats.zone_1_seconds,
            zone_2_seconds=stats.zone_2_seconds,
            zone_3_seconds=stats.zone_3_seconds,
            zone_4_seconds=stats.zone_4_seconds,
            zone_5_seconds=stats.zone_5_seconds,
        )

    @staticmethod
    def to_stats(snapshot: ActivityZoneSnapshot) -> HrZoneStats:
        """The stored per-zone seconds of a snapshot."""
        return HrZoneStats(
            zone_1_seconds=snapshot.zone_1_seconds,
            zone_2_seconds=snapshot.zone_2_seconds,
            zone_3_seconds=snapshot.zone_3_seconds,
            zone_4_seconds=snapshot.zone_4_seconds,
            zone_5_seconds=snapshot.zone_5_seconds,
        )
