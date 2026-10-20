"""UTC-deterministic datetimes for API views (M30).

The JSON contract is independent of the process timezone: a given instant
always renders as ISO 8601 UTC, whatever host the API runs on.

Why this exists: Postgres ``timestamptz`` values come back from psycopg
with the process's local offset attached (the wire value is an instant, and
psycopg renders it in the process TZ), and pydantic serializes an aware
datetime with whatever offset it carries. On a non-UTC host the same row
therefore serialized as e.g. ``2026-05-31T17:00:00-08:00`` instead of the
UTC rendering a UTC container produces. Normalizing at view construction
closes that gap for every datetime field at once: the shared validator
converts each aware instant to UTC (same instant, offset +00:00), and
pydantic's own serializer then renders it in the established wire format.

Every ``datetime`` field on a view must be typed as :data:`UtcDateTime`.
Naive datetimes are rejected: there is no host-independent way to render a
naive instant, and the app only ever carries aware ones (stored as UTC
``timestamptz``, parsed or built with an explicit offset).
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic.functional_validators import BeforeValidator


def to_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC (same instant, offset +00:00)."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("view datetimes must be timezone-aware")
    return value.astimezone(UTC)


#: A view datetime: an aware instant, always serialized as ISO 8601 UTC.
UtcDateTime = Annotated[datetime, BeforeValidator(to_utc)]
