"""Canonical sport types and mapping from vendor labels.

Vendor files spell the same sport many different ways ("Run", "running",
"Run Mode", "Trail Run", ...). ``resolve_sport`` folds them into the small
set the application stores.
"""

#: Every sport type the application supports, in display order.
SPORT_TYPES: tuple[str, ...] = (
    "running",
    "cycling",
    "rowing",
    "strength",
    "yoga",
    "hiking",
    "walking",
    "swimming",
    "other",
)

#: Sport assigned when an uploaded file carries no sport information at all.
DEFAULT_SPORT = "running"

_UNKNOWN_SPORT = "other"

_VENDOR_SPORT_MAP: dict[str, str] = {
    "running": "running",
    "run": "running",
    "run mode": "running",
    "marathon": "running",
    "trail run": "running",
    "treadmill": "running",
    "cycling": "cycling",
    "bike": "cycling",
    "bike ride": "cycling",
    "cycling mode": "cycling",
    "indoor bike": "cycling",
    "indoor cycling": "cycling",
    "virtual ride": "cycling",
    "mountain bike": "cycling",
    "spinning": "cycling",
    "rowing": "rowing",
    "indoor rower": "rowing",
    "indoor rowing": "rowing",
    "rowing machine": "rowing",
    "strength training": "strength",
    "strength": "strength",
    "weight training": "strength",
    "weights": "strength",
    "yoga": "yoga",
    "hiking": "hiking",
    "hike": "hiking",
    "trail": "hiking",
    "walking": "walking",
    "walk": "walking",
    "swimming": "swimming",
    "swim": "swimming",
    "open water swim": "swimming",
    "pool swim": "swimming",
}


def resolve_sport(raw: str | None) -> str | None:
    """Map a vendor sport label to a canonical sport type.

    Returns ``None`` when the file carries no sport information at all,
    ``"other"`` when it carries a label this application does not
    recognize, and the matching canonical type otherwise.
    """
    if raw is None or not raw.strip():
        return None
    return _VENDOR_SPORT_MAP.get(raw.strip().lower(), _UNKNOWN_SPORT)
