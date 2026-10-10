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


def group_duplicates(primaries: list[DuplicateSignals]) -> list[list[int]]:
    """Group ``primaries`` into clusters that look like the same workout (M29a).

    The library-wide retroactive half of M28: instead of matching one new row
    against the rest, it finds every duplicate cluster among a set of rows. It
    reuses :func:`find_duplicates` as the pairwise rule — for each row it asks,
    "which *later* rows of the same sport match me?" — and merges transitive
    matches (A~B and B~C are one cluster) with a union-find.

    ``primaries`` must be ordered so that same-sport entries are contiguous and
    in start-time order (that is the shape ``ActivityDao.list_live_primaries_for_user``
    returns). Each pair of rows is compared exactly once (an anchor only looks at
    later neighbours), so the result does not depend on scan order.

    Returns groups as lists of indices into ``primaries``: every group has at
    least two members, members are in ascending index (i.e. start-time) order, and
    the groups themselves are ordered by each group's earliest member. Rows that
    match nothing (singletons) are omitted — they are not duplicates of anything.

    Pure and deterministic, like :func:`find_duplicates`: no users, sessions or
    providers. The service owns the query that supplies the ordered rows and what
    to do with each group (a human confirms before linking, so nothing auto-acts).
    """
    count = len(primaries)

    # Union-find over row indices. The smaller (earlier) index always becomes the
    # root of its cluster, so a group's key is deterministically its first member.
    roots = list(range(count))

    def find(node: int) -> int:
        # Path halving: walk to the root, pulling each node up toward it.
        while roots[node] != node:
            roots[node] = roots[roots[node]]
            node = roots[node]
        return node

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a == root_b:
            return
        # The smaller index always wins, so the group key is its earliest member.
        if root_b < root_a:
            roots[root_a] = root_b
        else:
            roots[root_b] = root_a

    run_start = 0
    while run_start < count:
        sport_type = primaries[run_start].sport_type
        # End of the contiguous same-sport run starting at ``run_start``.
        run_end = run_start
        while run_end < count and primaries[run_end].sport_type == sport_type:
            run_end += 1

        for anchor in range(run_start, run_end):
            # Candidate window: the later same-sport rows that started within the
            # tolerance. The run is start-ordered, so once a follower starts too far
            # ahead every later one does as well — stop there.
            anchor_start = primaries[anchor].started_at_utc_seconds
            candidate_indices: list[int] = []
            for follower in range(anchor + 1, run_end):
                gap = primaries[follower].started_at_utc_seconds - anchor_start
                if gap > TIME_TOLERANCE_SECONDS:
                    break
                candidate_indices.append(follower)

            matches = find_duplicates(primaries[anchor], [primaries[f] for f in candidate_indices])
            # ``match.index`` indexes the (follower) list just built, whose order is
            # candidate_indices — so map it back to the row's global index.
            for match in matches:
                union(anchor, candidate_indices[match.index])

        run_start = run_end

    members: dict[int, list[int]] = {}
    for index in range(count):
        root = find(index)
        members.setdefault(root, []).append(index)

    groups: list[list[int]] = [indices for indices in members.values() if len(indices) >= 2]
    groups.sort(key=lambda group: (primaries[group[0]].started_at_utc_seconds, group[0]))
    return groups
