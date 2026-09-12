/** Unit tests for the dashboard period model (local + named-zone boundaries). */

import { describe, expect, it } from "vitest";

import {
  DEFAULT_PERIOD,
  periodRange,
  readStoredPeriod,
  storePeriod,
  zonedMidnightUtcMs,
} from "./periods";

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

describe("zonedMidnightUtcMs (M23b)", () => {
  it("lands on wall-clock midnight in a fixed-offset zone", () => {
    // Kiritimati is UTC+14 year-round: local midnight leads 14h in UTC, so
    // Sep 13T00:00 local = Sep 12T10:00Z.
    expect(zonedMidnightUtcMs(2026, 9, 13, "Pacific/Kiritimati")).toBe(
      Date.parse("2026-09-12T10:00:00Z"),
    );
  });

  it("follows the offset in force at that date (DST switch)", () => {
    // Berlin is CEST (+2) in October but switches to CET (+1) on 2026-10-25:
    // midnight Oct 1 = Sep 30T22:00Z (+2), but midnight Nov 1 = Oct 31T23:00Z (+1).
    expect(zonedMidnightUtcMs(2026, 10, 1, "Europe/Berlin")).toBe(Date.parse("2026-09-30T22:00:00Z"));
    expect(zonedMidnightUtcMs(2026, 11, 1, "Europe/Berlin")).toBe(Date.parse("2026-10-31T23:00:00Z"));
  });

  it("returns UTC midnight for a zone currently on UTC", () => {
    // London is GMT (+0) in winter.
    expect(zonedMidnightUtcMs(2026, 1, 15, "Europe/London")).toBe(Date.parse("2026-01-15T00:00:00Z"));
  });
});

describe("periodRange in a named zone (M23b)", () => {
  // Friday, 15:30 UTC. In LA (PDT −7) it is still Friday morning; in
  // Kiritimati (+14) it is already Saturday early morning.
  const friday = new Date("2026-09-11T15:30:00Z");

  it("day boundaries follow the zone's own calendar", () => {
    const la = periodRange("day", friday, "America/Los_Angeles");
    expect(la.start).toBe("2026-09-11T07:00:00.000Z"); // Fri 00:00 PDT
    expect(la.end).toBe("2026-09-12T07:00:00.000Z");

    const kir = periodRange("day", friday, "Pacific/Kiritimati"); // local date is already Sat Sep 12
    expect(kir.start).toBe("2026-09-11T10:00:00.000Z"); // Sat Sep 12T00:00 local − 14h
    expect(kir.end).toBe("2026-09-12T10:00:00.000Z"); // Sun Sep 13T00:00 local − 14h
  });

  it("the week starts on the Monday of that zone's calendar", () => {
    // Sunday 23:59Z = Sunday evening in LA, but Monday midday in Kiritimati —
    // different weeks for the same instant.
    const sundayNight = new Date("2026-09-13T23:59:00Z");
    const la = periodRange("week", sundayNight, "America/Los_Angeles");
    expect(la.start).toBe("2026-09-07T07:00:00.000Z"); // Mon Sep 7 (PDT)
    expect(la.end).toBe("2026-09-14T07:00:00.000Z");

    const kir = periodRange("week", sundayNight, "Pacific/Kiritimati"); // local date is Mon Sep 14
    expect(kir.start).toBe("2026-09-13T10:00:00.000Z"); // Mon Sep 14T00:00 local − 14h
    expect(kir.end).toBe("2026-09-20T10:00:00.000Z"); // Mon Sep 21T00:00 local − 14h
  });

  it("the month starts on the first of that zone's calendar", () => {
    // 03:00Z on Oct 1 is still Sep 30 (8pm PDT) in LA, but already October
    // in Berlin: different months for the same instant.
    const oct1 = new Date("2026-10-01T03:00:00Z");
    const la = periodRange("month", oct1, "America/Los_Angeles");
    expect(la.start).toBe("2026-09-01T07:00:00.000Z"); // Sep 1 (PDT)
    expect(la.end).toBe("2026-10-01T07:00:00.000Z");

    const berlin = periodRange("month", oct1, "Europe/Berlin"); // local date is already Oct 1
    expect(berlin.start).toBe("2026-09-30T22:00:00.000Z"); // Oct 1T00:00 local − CEST (+2)
    expect(berlin.end).toBe("2026-10-31T23:00:00.000Z"); // Nov 1T00:00 local − CET (+1, DST switched)
  });

  it("tz = null keeps the browser-local behaviour", () => {
    const range = periodRange("day", friday, null);
    expect(new Date(range.start).getTime()).toBe(
      new Date(friday.getFullYear(), friday.getMonth(), friday.getDate()).getTime(),
    );
    expect(new Date(range.end).getTime()).toBe(
      new Date(friday.getFullYear(), friday.getMonth(), friday.getDate() + 1).getTime(),
    );
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
