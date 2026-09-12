/** Unit tests for the display formatters (metric + imperial behaviour, time zones). */

import { describe, expect, it } from "vitest";

import {
  dayKey,
  dayLabel,
  formatActivityDate,
  formatClock,
  formatDistance,
  formatElevation,
  formatPace,
  formatWeight,
  paceSuffix,
} from "./format";

/** Full-date rendering in the default locale — used to assert "older day" labels. */
function fullDate(year: number, month1Based: number, day: number): string {
  return new Date(year, month1Based - 1, day).toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

describe("formatDistance", () => {
  it("renders metric meters below a kilometre", () => {
    expect(formatDistance(132, "metric")).toBe("132 m");
  });

  it("renders metric kilometres at two decimals", () => {
    expect(formatDistance(5054.3, "metric")).toBe("5.05 km");
  });

  it("renders imperial miles at one decimal", () => {
    expect(formatDistance(3.1406, "imperial")).toBe("3.1 mi");
  });

  it("renders an em dash for a missing value", () => {
    expect(formatDistance(null)).toBe("—");
  });
});

describe("formatElevation", () => {
  it("renders whole feet in imperial", () => {
    expect(formatElevation(393.7, "imperial")).toBe("394 ft");
  });

  it("keeps the metric behaviour (like a distance)", () => {
    expect(formatElevation(88, "metric")).toBe("88 m");
  });

  it("renders an em dash for a missing value", () => {
    expect(formatElevation(null, "imperial")).toBe("—");
  });
});

describe("formatWeight", () => {
  // The API already converts (M14): an imperial caller's value arrives in lb.
  // The formatter only rounds and labels — it never converts again.
  it("renders whole lb for imperial callers and kg otherwise", () => {
    expect(formatWeight(221.3, "imperial")).toBe("221 lb");
    expect(formatWeight(100.4, "metric")).toBe("100 kg");
  });

  it("renders an em dash for a missing value", () => {
    expect(formatWeight(null)).toBe("—");
  });
});

describe("paceSuffix", () => {
  it("is /km for metric (the default) and /mi otherwise", () => {
    expect(paceSuffix("metric")).toBe("/km");
    expect(paceSuffix()).toBe("/km");
    expect(paceSuffix("imperial")).toBe("/mi");
  });
});

describe("formatPace", () => {
  it('renders the m\'ss" style', () => {
    expect(formatPace(292.8)).toBe('4\'53"');
    expect(formatPace(0)).toBe('0\'00"');
  });

  it("renders an em dash for missing values", () => {
    expect(formatPace(null)).toBe("—");
    expect(formatPace(undefined)).toBe("—");
  });
});

describe("dayKey (M23b time zones)", () => {
  // Friday 15:30 UTC = Fri morning in LA (PDT −7), already Saturday in
  // Kiritimati (+14). The same instant must key to different calendar days.
  const iso = "2026-09-11T15:30:00Z";

  it("maps one instant to different calendar days in distant zones", () => {
    expect(dayKey(iso, "America/Los_Angeles")).toBe("2026-09-11");
    expect(dayKey(iso, "Pacific/Kiritimati")).toBe("2026-09-12");
  });

  it("defaults to the browser's local zone (the pre-M23b behaviour)", () => {
    const date = new Date(iso);
    const localKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${
      String(date.getDate()).padStart(2, "0")
    }`;
    expect(dayKey(iso)).toBe(localKey);
  });

  it("treats an empty-string zone like the browser default", () => {
    expect(dayKey(iso, "")).toBe(dayKey(iso));
  });

  it("dayLabel: Today/Yesterday are resolved in the zone (injected now)", () => {
    const now = new Date(iso);
    expect(dayLabel("2026-09-12", "Pacific/Kiritimati", now)).toBe("Today");
    expect(dayLabel("2026-09-11", "Pacific/Kiritimati", now)).toBe("Yesterday");
    expect(dayLabel("2026-09-11", "America/Los_Angeles", now)).toBe("Today");
    expect(dayLabel("2026-09-10", "America/Los_Angeles", now)).toBe("Yesterday");
  });

  it("dayLabel: older days render the full date", () => {
    const now = new Date(iso);
    expect(dayLabel("2026-09-10", "Pacific/Kiritimati", now)).toBe(fullDate(2026, 9, 10));
    expect(dayLabel("2026-08-30", "America/Los_Angeles", now)).toBe(fullDate(2026, 8, 30));
  });
});

describe("time formatters in a zone (M23b)", () => {
  const iso = "2026-09-11T15:30:00Z";

  it("formatClock renders the wall-clock time of the zone", () => {
    // Same expectation computed independently: 15:30Z is 29:30 the next day
    // in Kiritimati, i.e. 5:30 — so the zoned clock differs from UTC by +14h.
    expect(formatClock(iso, "Pacific/Kiritimati")).toBe(
      new Date(iso).toLocaleTimeString(undefined, {
        timeZone: "Pacific/Kiritimati",
        hour: "2-digit",
        minute: "2-digit",
      }),
    );
    expect(formatClock(iso, "Pacific/Kiritimati")).not.toBe(
      new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
    );
  });

  it("formatActivityDate flips the calendar date across midnight", () => {
    // Fri in LA, Sat in Kiritimati: the short date must carry each zone's day.
    const expected = (timeZone: string) =>
      new Date(iso).toLocaleDateString(undefined, {
        timeZone,
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    expect(formatActivityDate(iso, "Pacific/Kiritimati")).toBe(expected("Pacific/Kiritimati"));
    expect(formatActivityDate(iso, "America/Los_Angeles")).toBe(expected("America/Los_Angeles"));
    expect(formatActivityDate(iso, "Pacific/Kiritimati")).not.toBe(
      formatActivityDate(iso, "America/Los_Angeles"),
    );
  });

  it("both formatters default to the browser's local zone", () => {
    const date = new Date(iso);
    expect(formatClock(iso)).toBe(
      date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
    );
    expect(formatActivityDate(iso)).toBe(
      date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }),
    );
  });
});
