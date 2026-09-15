"""Cross-source duplicate detection (M28a): pure, deterministic matching.

The same physical workout can arrive through different sources — a GPX export
uploaded as a file and the identical run in a provider feed, or (later) two
providers. There is no shared external id across sources, so matching is
heuristic but deliberately conservative: a false positive hides one of the
user's activities, so the bar is "almost certainly the same workout".

The rule (all comparisons on UTC instants — never wall-clock strings):
  * same sport type, and
  * start times within TIME_TOLERANCE of each other (device clock drift and
    export round-trips stay in the seconds-to-minutes), and
  * at least one aligned metric: duration within max(DURATION_RELATIVE,
    DURATION_MIN_SECONDS), or — when both carry a distance — distances within
    DISTANCE_RELATIVE of each other (manufacturer GPS smoothing differs by low
    single-digit percent; the tolerance is set wider than that).

Activities without a distance (indoor, strength) match on time + duration
alone — inside the tight start-time window that is already a strong signal.

This module knows nothing about users, sessions or providers: it takes plain
numbers and returns scores. The service layer owns the query that supplies
candidates (live, unlinked primaries in a widened time window) and what to do
with the matches.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DuplicateSignals:
    """The fields the matcher looks at — everything else is irrelevant."""

    sport_type: str
    started_at_utc_seconds: float  # epoch seconds, timezone-free by construction
    duration_seconds: int | None
    distance_m: float | None


@dataclass(frozen=True)
class DuplicateCandidate:
    """A matched existing activity and how strongly it matches."""

    index: int  # position of the match in the ``existing`` list passed to find
    delta_seconds: float  # |start difference|, the primary match strength


# Start times closer than this are "the same moment" for matching purposes.
TIME_TOLERANCE_SECONDS = 30 * 60

# Duration must agree within the larger of this absolute floor (short efforts)
# and 5% of it (long efforts).
DURATION_MIN_SECONDS = 60.0
DURATION_RELATIVE = 0.05

# Distances may differ by up to this fraction (GPS smoothing differences).
DISTANCE_RELATIVE = 0.10


def _duration_close(a: int | None, b: int | None) -> bool:
    if a is None or b is None:
        return False
    base = max(a, b)
    tolerance = max(DURATION_MIN_SECONDS, DURATION_RELATIVE * base)
    return abs(a - b) <= tolerance


def _distance_close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return False
    base = max(a, b)
    if base == 0:
        return a == b
    return abs(a - b) <= DISTANCE_RELATIVE * base


def find_duplicates(
    new: DuplicateSignals, existing: list[DuplicateSignals]
) -> list[DuplicateCandidate]:
    """The entries of ``existing`` that match ``new``, strongest (closest start) first."""
    matches: list[DuplicateCandidate] = []
    for index, candidate in enumerate(existing):
        if candidate.sport_type != new.sport_type:
            continue
        delta = abs(candidate.started_at_utc_seconds - new.started_at_utc_seconds)
        if delta > TIME_TOLERANCE_SECONDS:
            continue
        duration_ok = _duration_close(new.duration_seconds, candidate.duration_seconds)
        distance_ok = _distance_close(new.distance_m, candidate.distance_m)
        if duration_ok or distance_ok:
            matches.append(DuplicateCandidate(index=index, delta_seconds=delta))
    return sorted(matches, key=lambda match: (match.delta_seconds, match.index))
