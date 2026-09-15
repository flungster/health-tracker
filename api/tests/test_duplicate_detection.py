"""Unit tests for the pure cross-source duplicate matcher (M28a)."""

from app.services.duplicate_detection import (
    DuplicateSignals,
    find_duplicates,
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
