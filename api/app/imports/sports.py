"""Canonical sport types and mapping from vendor labels.

Vendor files spell the same sport many different ways ("Run", "running",
"Run Mode", "Trail Run", ...). ``resolve_sport`` folds them into the small
set the application stores.

The value set below is the code-side mirror of the ``activity_types``
reference table (the schema-level source of truth): the enum's values must
match the seeded rows, and ``activities.sport_type`` carries a foreign key
to ``activity_types.value``.
"""

from enum import StrEnum


class SportType(StrEnum):
    """Canonical sport types (values match the activity_types reference table)."""

    RUNNING = "running"
    CYCLING = "cycling"
    ROWING = "rowing"
    STRENGTH = "strength"
    YOGA = "yoga"
    HIKING = "hiking"
    WALKING = "walking"
    SWIMMING = "swimming"
    OTHER = "other"


#: Every sport type the application supports, in display order.
SPORT_TYPES: tuple[str, ...] = tuple(member.value for member in SportType)

#: Sport assigned when an uploaded file carries no sport information at all.
DEFAULT_SPORT: SportType = SportType.RUNNING

_UNKNOWN_SPORT: SportType = SportType.OTHER

_VENDOR_SPORT_MAP: dict[str, SportType] = {
    "running": SportType.RUNNING,
    "run": SportType.RUNNING,
    "run mode": SportType.RUNNING,
    "marathon": SportType.RUNNING,
    "trail run": SportType.RUNNING,
    "treadmill": SportType.RUNNING,
    "cycling": SportType.CYCLING,
    "bike": SportType.CYCLING,
    "bike ride": SportType.CYCLING,
    "cycling mode": SportType.CYCLING,
    "indoor bike": SportType.CYCLING,
    "indoor cycling": SportType.CYCLING,
    "virtual ride": SportType.CYCLING,
    "mountain bike": SportType.CYCLING,
    "spinning": SportType.CYCLING,
    "rowing": SportType.ROWING,
    "indoor rower": SportType.ROWING,
    "indoor rowing": SportType.ROWING,
    "rowing machine": SportType.ROWING,
    "strength training": SportType.STRENGTH,
    "strength": SportType.STRENGTH,
    "weight training": SportType.STRENGTH,
    "weights": SportType.STRENGTH,
    "yoga": SportType.YOGA,
    "hiking": SportType.HIKING,
    "hike": SportType.HIKING,
    "trail": SportType.HIKING,
    "walking": SportType.WALKING,
    "walk": SportType.WALKING,
    "swimming": SportType.SWIMMING,
    "swim": SportType.SWIMMING,
    "open water swim": SportType.SWIMMING,
    "pool swim": SportType.SWIMMING,
}


def resolve_sport(raw: str | None) -> SportType | None:
    """Map a vendor sport label to a canonical sport type.

    Returns ``None`` when the file carries no sport information at all,
    ``SportType.OTHER`` when it carries a label this application does not
    recognize, and the matching type otherwise. (``SportType`` is a
    ``str`` enum, so results compare equal to the plain value strings.)
    """
    if raw is None or not raw.strip():
        return None
    return _VENDOR_SPORT_MAP.get(raw.strip().lower(), _UNKNOWN_SPORT)
