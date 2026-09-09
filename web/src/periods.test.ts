/** Unit tests for the dashboard period model (local-timezone boundaries). */

import { describe, expect, it } from "vitest";

import { DEFAULT_PERIOD, periodRange, readStoredPeriod, storePeriod } from "./periods";

// All dates are constructed in local time; the returned instants (UTC ISO)
// must land on exactly those local boundaries, whatever timezone runs the test.

describe("periodRange", () => {
  it("day: local midnight to the next, from any time of day", () => {
    const range = periodRange("day", new Date(2026, 8, 9, 15, 30));

    expect(new Date(range.start).getTime()).toBe(new Date(2026, 8, 9).getTime());
    expect(new Date(range.end).getTime()).toBe(new Date(2026, 8, 10).getTime());
  });

  it("week: Monday to the following Monday, from a mid-week day", () => {
    const range = periodRange("week", new Date(2026, 8, 9, 3, 15)); // Wednesday

    expect(new Date(range.start).getTime()).toBe(new Date(2026, 8, 7).getTime()); // Monday
    expect(new Date(range.end).getTime()).toBe(new Date(2026, 8, 14).getTime()); // next Monday
  });

  it("week: a Monday starts its own week", () => {
    const range = periodRange("week", new Date(2026, 8, 7));

    expect(new Date(range.start).getTime()).toBe(new Date(2026, 8, 7).getTime());
    expect(new Date(range.end).getTime()).toBe(new Date(2026, 8, 14).getTime());
  });

  it("week: a Sunday belongs to the week ending that day", () => {
    const range = periodRange("week", new Date(2026, 8, 13)); // Sunday

    expect(new Date(range.start).getTime()).toBe(new Date(2026, 8, 7).getTime());
    expect(new Date(range.end).getTime()).toBe(new Date(2026, 8, 14).getTime());
  });

  it("week: crosses a month (and year) boundary", () => {
    // Saturday Jan 3, 2026 — its week starts on the Monday before New Year.
    const range = periodRange("week", new Date(2026, 0, 3));

    expect(new Date(range.start).getTime()).toBe(new Date(2025, 11, 29).getTime()); // Monday Dec 29
    expect(new Date(range.end).getTime()).toBe(new Date(2026, 0, 5).getTime()); // Monday Jan 5
  });

  it("month: first of the month to the next, mid-month and across a year", () => {
    const september = periodRange("month", new Date(2026, 8, 9));
    expect(new Date(september.start).getTime()).toBe(new Date(2026, 8, 1).getTime());
    expect(new Date(september.end).getTime()).toBe(new Date(2026, 9, 1).getTime());

    const december = periodRange("month", new Date(2026, 11, 20));
    expect(new Date(december.start).getTime()).toBe(new Date(2026, 11, 1).getTime());
    expect(new Date(december.end).getTime()).toBe(new Date(2027, 0, 1).getTime());
  });

  it("year: January 1 to the next, in any month", () => {
    const range = periodRange("year", new Date(2026, 8, 9));

    expect(new Date(range.start).getTime()).toBe(new Date(2026, 0, 1).getTime());
    expect(new Date(range.end).getTime()).toBe(new Date(2027, 0, 1).getTime());
  });

  it("ranges are half-open and contiguous across a rollover", () => {
    const today = periodRange("day", new Date(2026, 8, 9));
    const tomorrow = periodRange("day", new Date(2026, 8, 10));

    expect(new Date(tomorrow.start).getTime()).toBe(new Date(today.end).getTime());
  });
});

describe("stored period preference", () => {
  it("falls back to the default when nothing (or junk) is stored", () => {
    window.localStorage.clear();
    expect(readStoredPeriod()).toBe(DEFAULT_PERIOD);

    window.localStorage.setItem("health-tracker.dashboard.period", "fortnight");
    expect(readStoredPeriod()).toBe(DEFAULT_PERIOD);
  });

  it("round-trips a valid choice", () => {
    storePeriod("month");
    expect(readStoredPeriod()).toBe("month");

    window.localStorage.clear();
  });
});
