"""Timestamp and duration helpers shared by the activity parsers."""

import re
from datetime import UTC, datetime

_ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?")


def to_utc(value: datetime | None) -> datetime | None:
    """Normalize a timestamp to UTC.

    Naive timestamps are assumed to already be UTC (the common case for
    device exports) and are simply tagged as such.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_iso8601(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp, returning UTC or None when unparseable."""
    if value is None:
        return None
    try:
        return to_utc(datetime.fromisoformat(value.strip()))
    except ValueError:
        return None


def parse_iso_duration_seconds(value: str | None) -> int | None:
    """Parse an ISO 8601 duration such as ``PT1H2M30S`` into whole seconds."""
    if value is None:
        return None
    match = _ISO_DURATION_RE.fullmatch(value.strip())
    if match is None:
        return None
    hours, minutes, seconds = match.groups()
    total = int(hours or 0) * 3600 + int(minutes or 0) * 60
    if seconds:
        total += int(float(seconds))
    return total
