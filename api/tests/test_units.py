"""Unit tests for the pure display-unit conversion helpers (app.schemas.units).

The factors are exact definitions, so where a value is divided by the same
constant it was defined with (e.g. one mile in meters / MILE_METERS), the
result is exactly 1.0; everything else is checked with a tight relative bound.
"""

from datetime import UTC, datetime

import pytest

from app.schemas.units import (
    FOOT_METERS,
    MILE_METERS,
    POUND_KILOGRAMS,
    UnitSystem,
    display_altitude,
    display_distance,
    display_elevation_gain,
    display_pace_seconds,
    display_speed,
    display_weight,
    units_for,
)


class TestUnitsFor:
    def test_unset_setting_is_metric(self) -> None:
        assert units_for(None) is UnitSystem.METRIC

    def test_set_setting_is_imperial(self) -> None:
        assert units_for(datetime(2026, 9, 5, tzinfo=UTC)) is UnitSystem.IMPERIAL

    def test_enum_values_are_the_public_strings(self) -> None:
        assert UnitSystem.METRIC.value == "metric"
        assert UnitSystem.IMPERIAL.value == "imperial"


class TestConversions:
    def test_none_passes_through_every_converter(self) -> None:
        assert display_distance(None, UnitSystem.IMPERIAL) is None
        assert display_elevation_gain(None, UnitSystem.IMPERIAL) is None
        assert display_altitude(None, UnitSystem.IMPERIAL) is None
        assert display_speed(None, UnitSystem.IMPERIAL) is None
        assert display_pace_seconds(None, UnitSystem.IMPERIAL) is None
        assert display_weight(None, UnitSystem.IMPERIAL) is None

    def test_metric_returns_the_stored_value_unchanged(self) -> None:
        assert display_distance(123.456, UnitSystem.METRIC) == 123.456
        assert display_elevation_gain(123.456, UnitSystem.METRIC) == 123.456
        assert display_altitude(123.456, UnitSystem.METRIC) == 123.456
        assert display_speed(7.2, UnitSystem.METRIC) == 7.2
        assert display_pace_seconds(305.0, UnitSystem.METRIC) == 305.0
        assert display_weight(82.5, UnitSystem.METRIC) == 82.5

    def test_one_mile_is_exactly_one(self) -> None:
        assert display_distance(MILE_METERS, UnitSystem.IMPERIAL) == 1.0

    def test_one_foot_is_exactly_one(self) -> None:
        assert display_elevation_gain(FOOT_METERS, UnitSystem.IMPERIAL) == 1.0
        assert display_altitude(FOOT_METERS, UnitSystem.IMPERIAL) == 1.0

    def test_one_pound_is_exactly_one(self) -> None:
        assert display_weight(POUND_KILOGRAMS, UnitSystem.IMPERIAL) == 1.0

    def test_distance_round_trip_loses_nothing_practical(self) -> None:
        miles = display_distance(5021.0, UnitSystem.IMPERIAL)  # ~3.1 mi
        assert miles is not None
        back = miles * MILE_METERS
        assert back == pytest.approx(5021.0, rel=1e-12)

    def test_pace_scales_by_the_exact_mile_km_ratio(self) -> None:
        # 300 s/km = a 5'00" pace -> exactly 482.8032 s/mi (x1.609344).
        assert display_pace_seconds(300.0, UnitSystem.IMPERIAL) == pytest.approx(482.8032, rel=1e-9)

    def test_speed_converts_to_mph(self) -> None:
        # 5 m/s = 18000 m/h / 1609.344 m/mi.
        assert display_speed(5.0, UnitSystem.IMPERIAL) == pytest.approx(
            18000.0 / MILE_METERS, rel=1e-9
        )

    def test_weight_converts_to_lb(self) -> None:
        # 70 kg = ~154.3 lb (x2.20462...).
        assert display_weight(70.0, UnitSystem.IMPERIAL) == pytest.approx(
            70.0 / POUND_KILOGRAMS, rel=1e-9
        )
