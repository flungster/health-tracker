"""Unit tests for the pure cross-source duplicate matcher (M28a).

``group_duplicates`` (M29a) is the library-wide retroactive half: it reuses
:func:`find_duplicates` as its pairwise rule, so these tests pin down that the
scan applies exactly M28's conservative rules — same sport, start within 30 min,
duration or distance aligned — and merges transitive matches into clusters.
"""

from app.services.duplicate_detection import (
    DuplicateSignals,
    find_duplicates,
    group_duplicates,
)


def _signals(
    started: float = 0.0,
    sport_type: str = "Running",
    duration: int | None = 3000,
    distance: float | None = 10_000.0,
) -> DuplicateSignals:
    return DuplicateSignals(
        sport_type=sport_type,
        started_at_utc_seconds=started,
        duration_seconds=duration,
        distance_m=distance,
    )


class TestFindDuplicates:
    def test_exact_match(self) -> None:
        existing = [_signals(), _signals(started=3_600)]
        matches = find_duplicates(_signals(), existing)
        assert [match.index for match in matches] == [0]
        assert matches[0].delta_seconds == 0.0

    def test_clock_drift_within_tolerance_matches(self) -> None:
        # 12 minutes of drift (device clock vs export round-trip) is a match.
        matches = find_duplicates(_signals(started=12 * 60), [_signals()])
        assert [match.index for match in matches] == [0]

    def test_start_beyond_half_hour_is_not_a_match(self) -> None:
        matches = find_duplicates(_signals(started=31 * 60), [_signals()])
        assert matches == []

    def test_different_sport_type_never_matches(self) -> None:
        matches = find_duplicates(
            _signals(sport_type="Cycling"), [_signals(started=0, sport_type="Running")]
        )
        assert matches == []

    def test_duration_mismatch_beyond_tolerance_rejects(self) -> None:
        # 30 min vs 60 min effort at the same start time: different workouts.
        # (No distance, so duration is the only metric to align.)
        matches = find_duplicates(
            _signals(duration=1800, distance=None),
            [_signals(started=60, duration=3600, distance=None)],
        )
        assert matches == []

    def test_duration_within_five_percent_matches(self) -> None:
        # 50 min vs 52 min (4% apart): the same effort, slightly different clock.
        matches = find_duplicates(
            _signals(duration=3000, distance=None),
            [_signals(started=90, duration=3125, distance=None)],
        )
        assert [match.index for match in matches] == [0]

    def test_short_efforts_use_the_absolute_floor(self) -> None:
        # 45s vs 90s is 100% apart, but under the 60s floor for short efforts.
        matches = find_duplicates(
            _signals(duration=45, distance=None),
            [_signals(started=10, duration=90, distance=None)],
        )
        assert [match.index for match in matches] == [0]

    def test_distance_withins_ten_percent_matches_even_when_duration_differs(self) -> None:
        # GPS smoothing can disagree with the clock; a 9% distance gap still matches.
        new = _signals(duration=3000, distance=10_000.0)
        existing = _signals(started=300, duration=2950, distance=10_850.0)
        matches = find_duplicates(new, [existing])
        assert [match.index for match in matches] == [0]

    def test_distance_beyond_ten_percent_rejects(self) -> None:
        new = _signals(duration=3000, distance=10_000.0)
        existing = _signals(started=300, duration=None, distance=12_500.0)
        assert find_duplicates(new, [existing]) == []

    def test_no_distance_uses_time_and_duration_only(self) -> None:
        # Indoor/strength rows carry no distance; time + duration is enough.
        new = _signals(duration=20 * 60, distance=None)
        existing = [
            _signals(started=300, duration=21 * 60, distance=None),
            _signals(started=3600 * 24, duration=21 * 60, distance=None),
        ]
        matches = find_duplicates(new, existing)
        assert [match.index for match in matches] == [0]

    def test_missing_metrics_on_both_sides_never_match(self) -> None:
        # No duration and no distance on either row: nothing to align.
        new = _signals(duration=None, distance=None)
        existing = [_signals(started=60, duration=None, distance=None)]
        assert find_duplicates(new, existing) == []

    def test_zero_distances_match_only_when_equal(self) -> None:
        new = _signals(duration=None, distance=0.0)
        assert find_duplicates(new, [_signals(started=10, distance=0.0)])
        assert find_duplicates(new, [_signals(started=10, distance=5.0)]) == []

    def test_strongest_match_comes_first(self) -> None:
        new = _signals()
        existing = [
            _signals(started=20 * 60),  # index 0: farther
            _signals(started=5 * 60),  # index 1: closer
        ]
        matches = find_duplicates(new, existing)
        assert [match.index for match in matches] == [1, 0]

    def test_no_existing_rows(self) -> None:
        assert find_duplicates(_signals(), []) == []


class TestGroupDuplicates:
    """The library-wide scanner's pure clustering step (M29a), reusing the matcher."""

    def test_no_rows(self) -> None:
        assert group_duplicates([]) == []

    def test_a_single_row_is_not_a_duplicate(self) -> None:
        # Nothing to pair with; singletons are never reported.
        assert group_duplicates([_signals()]) == []

    def test_two_identical_rows_form_one_group_in_start_order(self) -> None:
        rows = [_signals(started=0.0), _signals(started=120.0)]
        assert group_duplicates(rows) == [[0, 1]]

    def test_time_gap_beyond_tolerance_is_not_grouped(self) -> None:
        # 31 minutes apart (the matcher's window is half an hour): different workouts,
        # even though every metric lines up. Proves the 30-min rule flows through.
        rows = [_signals(started=0.0), _signals(started=31 * 60)]
        assert group_duplicates(rows) == []

    def test_different_sports_never_group(self) -> None:
        # Same instant, same metrics — but a run and a ride are different workouts.
        rows = [
            _signals(started=0.0, sport_type="running"),
            _signals(started=0.0, sport_type="cycling"),
        ]
        assert group_duplicates(rows) == []

    def test_metrics_must_still_align_within_the_window(self) -> None:
        # Same sport, same instant — but a 30-min and a 60-min effort are different
        # workouts (no distance to fall back on), so no group. Reuses the matcher's
        # duration rule, not just its time/sport gates.
        rows = [
            _signals(started=0.0, duration=1800, distance=None),
            _signals(started=60.0, duration=3600, distance=None),
        ]
        assert group_duplicates(rows) == []

    def test_transitive_matches_merge_into_one_cluster(self) -> None:
        # A~B (25 min apart) and B~C (23 min apart), but A and C are 48 min apart —
        # beyond the window, so only B bridges them. The cluster is still all three:
        # A~B~C, even though no pair of (A, C) matches directly.
        rows = [
            _signals(started=0 * 60),  # A — index 0
            _signals(started=25 * 60),  # B — index 1
            _signals(started=48 * 60),  # C — index 2
        ]
        assert group_duplicates(rows) == [[0, 1, 2]]

    def test_singletons_are_dropped(self) -> None:
        # A matching running pair plus an unrelated lone ride (different sport and far
        # away in time): only the run pair is reported. Input ordered by (sport, start).
        rows = [
            _signals(started=86_400, sport_type="cycling"),  # index 0 — lone ride
            _signals(started=0.0, sport_type="running"),  # index 1 — run A
            _signals(started=60.0, sport_type="running"),  # index 2 — run A's twin
        ]
        assert group_duplicates(rows) == [[1, 2]]

    def test_groups_are_ordered_by_each_earliest_start(self) -> None:
        # A cycling pair that started before a running pair; the earlier-start group
        # comes first in the result. Input ordered by (sport, start).
        rows = [
            _signals(started=0.0, sport_type="cycling"),  # index 0 — ride A
            _signals(started=60.0, sport_type="cycling"),  # index 1 — ride A's twin
            _signals(started=3600.0, sport_type="running"),  # index 2 — run
            _signals(started=4000.0, sport_type="running"),  # index 3 — run's twin
        ]
        assert group_duplicates(rows) == [[0, 1], [2, 3]]

    def test_distance_alignment_can_bridge_a_duration_mismatch(self) -> None:
        # The clock disagrees (9% off, like GPS smoothing), but the distances agree —
        # still one workout. Mirrors find_duplicates' "duration OR distance" rule.
        rows = [
            _signals(started=0.0, duration=3000, distance=10_000.0),  # index 0
            _signals(started=300, duration=2950, distance=10_850.0),  # index 1
        ]
        assert group_duplicates(rows) == [[0, 1]]

    def test_many_rows_group_into_several_clusters(self) -> None:
        # Four running twins clustered in two pairs 2 hours apart (each pair within the
        # window, pairs far enough apart to stay separate), plus an unrelated walk.
        rows = [
            _signals(started=0, sport_type="running"),  # 0 — run A
            _signals(started=15 * 60, sport_type="running"),  # 1 — run A twin
            _signals(started=2 * 3600, sport_type="running"),  # 2 — run B
            _signals(started=15 * 60 + 2 * 3600, sport_type="running"),  # 3 — run B twin
            _signals(started=5 * 3600, sport_type="walking"),  # 4 — lone walk
        ]
        assert group_duplicates(rows) == [[0, 1], [2, 3]]

    def test_result_is_independent_of_member_durations(self) -> None:
        # The same cluster, but the two members disagree on duration (one exporter omits
        # it) and agree only via distance: still grouped, proving the OR-metric rule.
        rows = [
            _signals(started=0, duration=None, distance=12_000.0),  # 0
            _signals(started=90, duration=5400, distance=12_600.0),  # 1 (5% off)
        ]
        assert group_duplicates(rows) == [[0, 1]]
