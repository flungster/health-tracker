"""Resolve which heart-rate zone reference a user's profile currently defines.

A *zone reference* is the thing zones are computed against: either a set of
user-defined custom zone boundaries, or a max heart rate (entered manually or
derived from age via 220 - current_age). Resolution is a fixed precedence so
the active source is unambiguous:

    custom zones  >  manual max heart rate  >  age-derived max heart rate

The resolution is pure (profile + a reference date in, reference or None out)
so it can be unit-tested without a database. The per-zone computation
(``ActivityTrackpointDao``) consumes the resolved reference at view time.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.models.user_profile import UserProfile


class ZoneSource(StrEnum):
    """Where a zone computation's reference came from (mirrors ``zone_sources``)."""

    CUSTOM = "custom"
    MAX_HEART_RATE = "max_heart_rate"
    AGE = "age"


#: Max heart rate is estimated as ``AGE_MAX_HR_BASE - current_age``.
AGE_MAX_HR_BASE = 220


@dataclass(frozen=True)
class ZoneReference:
    """The resolved reference zones are computed against.

    Only the fields matching ``source`` are populated; the rest stay None so a
    snapshot can record exactly what was used.
    """

    source: ZoneSource
    max_heart_rate: int | None = None  # set for AGE and MAX_HEART_RATE
    age: int | None = None  # the derived age, for AGE (display)
    custom_zone_tops: tuple[int, int, int, int] | None = None  # for CUSTOM


def current_age(date_of_birth: date, today: date) -> int:
    """Whole years lived as of ``today`` (0 when the birthday hasn't occurred)."""
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )


def resolve_zone_reference(profile: UserProfile | None, today: date) -> ZoneReference | None:
    """Resolve the active zone reference for a profile, or None when none is set.

    Precedence: custom zones (all four thresholds present) > manual max heart
    rate > age-derived max heart rate. The age source is skipped when it would
    not yield a sensible max HR (e.g. an implausibly large age).
    """
    if profile is None:
        return None

    cz1 = profile.custom_zone_1_top_bpm
    cz2 = profile.custom_zone_2_top_bpm
    cz3 = profile.custom_zone_3_top_bpm
    cz4 = profile.custom_zone_4_top_bpm
    if cz1 is not None and cz2 is not None and cz3 is not None and cz4 is not None:
        return ZoneReference(source=ZoneSource.CUSTOM, custom_zone_tops=(cz1, cz2, cz3, cz4))

    if profile.max_heart_rate is not None:
        return ZoneReference(
            source=ZoneSource.MAX_HEART_RATE, max_heart_rate=profile.max_heart_rate
        )

    if profile.date_of_birth is not None:
        age = current_age(profile.date_of_birth, today)
        max_heart_rate = AGE_MAX_HR_BASE - age
        if age >= 1 and max_heart_rate > 0:
            return ZoneReference(source=ZoneSource.AGE, max_heart_rate=max_heart_rate, age=age)

    return None
