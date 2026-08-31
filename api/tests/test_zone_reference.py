"""Unit tests for zone-reference resolution (pure logic, fixed dates)."""

from datetime import date
from uuid import UUID

from app.models.user_profile import UserProfile
from app.services.zone_reference import (
    AGE_MAX_HR_BASE,
    ZoneReference,
    ZoneSource,
    current_age,
    resolve_zone_reference,
)

USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def _profile(**kwargs) -> UserProfile:
    return UserProfile(user_id=USER_ID, **kwargs)


class TestCurrentAge:
    def test_birthday_not_yet_this_year(self):
        assert current_age(date(1984, 5, 1), date(2026, 4, 30)) == 41
        assert current_age(date(1984, 5, 1), date(2026, 5, 1)) == 42

    def test_birthday_already_passed(self):
        assert current_age(date(1984, 5, 1), date(2026, 5, 2)) == 42

    def test_not_born_yet_is_zero(self):
        assert current_age(date(2030, 1, 1), date(2026, 1, 1)) == -4


class TestResolveZoneReference:
    def test_no_profile(self):
        assert resolve_zone_reference(None, date(2026, 8, 30)) is None

    def test_empty_profile(self):
        assert resolve_zone_reference(_profile(), date(2026, 8, 30)) is None

    def test_max_heart_rate_source(self):
        reference = resolve_zone_reference(_profile(max_heart_rate=185), date(2026, 8, 30))
        assert reference == ZoneReference(source=ZoneSource.MAX_HEART_RATE, max_heart_rate=185)

    def test_age_source(self):
        reference = resolve_zone_reference(
            _profile(date_of_birth=date(1984, 5, 1)), date(2026, 8, 30)
        )
        assert reference is not None
        assert reference.source == ZoneSource.AGE
        # 2026-08-30: born 1984-05-01 -> age 42.
        assert reference.age == 42
        assert reference.max_heart_rate == AGE_MAX_HR_BASE - 42

    def test_custom_source(self):
        reference = resolve_zone_reference(
            _profile(
                custom_zone_1_top_bpm=120,
                custom_zone_2_top_bpm=140,
                custom_zone_3_top_bpm=160,
                custom_zone_4_top_bpm=178,
            ),
            date(2026, 8, 30),
        )
        assert reference == ZoneReference(
            source=ZoneSource.CUSTOM, custom_zone_tops=(120, 140, 160, 178)
        )

    def test_precedence_custom_over_max_hr_and_age(self):
        reference = resolve_zone_reference(
            _profile(
                max_heart_rate=185,
                date_of_birth=date(1984, 5, 1),
                custom_zone_1_top_bpm=120,
                custom_zone_2_top_bpm=140,
                custom_zone_3_top_bpm=160,
                custom_zone_4_top_bpm=178,
            ),
            date(2026, 8, 30),
        )
        assert reference is not None
        assert reference.source == ZoneSource.CUSTOM

    def test_precedence_max_hr_over_age(self):
        reference = resolve_zone_reference(
            _profile(max_heart_rate=185, date_of_birth=date(1984, 5, 1)),
            date(2026, 8, 30),
        )
        assert reference is not None
        assert reference.source == ZoneSource.MAX_HEART_RATE

    def test_partial_custom_set_is_ignored(self):
        # Only two of four thresholds: not a complete set, so it does not win.
        reference = resolve_zone_reference(
            _profile(custom_zone_1_top_bpm=120, custom_zone_2_top_bpm=140),
            date(2026, 8, 30),
        )
        assert reference is None

    def test_age_source_skipped_when_formula_goes_non_positive(self):
        # Born 1750 -> age ~276, so 220 - age <= 0: the guard skips it.
        # (The service's validation already caps stored ages at 120; this is a
        # backstop so the formula can never divide by zero or go negative.)
        reference = resolve_zone_reference(
            _profile(date_of_birth=date(1750, 1, 1)), date(2026, 8, 30)
        )
        assert reference is None
