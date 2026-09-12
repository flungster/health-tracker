/** Dashboard period model: the four fixed segments and their [start, end) ranges.

The selection is display-only state (ADR M18): the client computes half-open
UTC instants for the period's calendar boundaries *in the user's display time
zone* (M23b; null = the browser's local zone — today's behavior), consistent
with the feed's Today / Yesterday grouping, and sends them to the summary
endpoint. No server state.
*/

export type Period = "day" | "week" | "month" | "year";

/** The selectable segments, in the order they appear in the UI. */
export const PERIODS: Period[] = ["day", "week", "month", "year"];

const STORAGE_KEY = "health-tracker.dashboard.period";
/** The first visit lands on the fullest view (chart + a week of cards). */
export const DEFAULT_PERIOD: Period = "week";

/** The card/heading label for a period ("This week", …). */
export function periodLabel(period: Period): string {
  switch (period) {
    case "day":
      return "Today";
    case "week":
      return "This week";
    case "month":
      return "This month";
    default:
      return "This year";
  }
}

export type PeriodRange = { start: string; end: string };

/** A wall-clock calendar date (no offset, no instant). */
type WallDate = { year: number; month0: number; day: number };

/** The zone's UTC offset at an instant, in ms (east positive). Parsed from
 *  Intl's "GMT±H[:MM]" short offset — no hand-rolled offset math. */
function zonedOffsetMs(instant: number, timeZone: string): number {
  const part = new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "shortOffset",
  })
    .formatToParts(new Date(instant))
    .find((p) => p.type === "timeZoneName");
  const match = /^GMT([+-])(\d{1,2})(?::(\d{2}))?$/.exec(part?.value ?? "GMT");
  if (match === null) {
    return 0; // bare "GMT": the zone is on UTC right now (e.g. London in winter)
  }
  const sign = match[1] === "-" ? -1 : 1;
  return sign * (Number(match[2]) * 3_600_000 + Number(match[3] ?? "0") * 60_000);
}

/** The UTC instant of midnight (wall clock) on a date in a zone. DST-safe:
 *  fixed-point iteration over the offset converges within a couple of passes,
 *  including across transitions. Exported for unit tests. */
export function zonedMidnightUtcMs(
  year: number,
  month1Based: number,
  day: number,
  timeZone: string,
): number {
  const targetAsUtc = Date.UTC(year, month1Based - 1, day); // wall midnight as if UTC
  let candidate = targetAsUtc;
  for (let i = 0; i < 4; i++) {
    const next = targetAsUtc - zonedOffsetMs(candidate, timeZone);
    if (next === candidate) {
      return candidate;
    }
    candidate = next;
  }
  // Unreachable for real zones: offsets move by hours, never days.
  return candidate;
}

/** The wall-clock calendar date of an instant in a zone (null = browser). */
function zonedDateParts(instant: Date, timeZone: string | null): WallDate {
  if (timeZone === null || timeZone.trim() === "") {
    return { year: instant.getFullYear(), month0: instant.getMonth(), day: instant.getDate() };
  }
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(instant);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? "0");
  return { year: get("year"), month0: get("month") - 1, day: get("day") };
}

function shiftDays(date: WallDate, by: number): WallDate {
  const shifted = new Date(Date.UTC(date.year, date.month0, date.day) + by * 86_400_000);
  return { year: shifted.getUTCFullYear(), month0: shifted.getUTCMonth(), day: shifted.getUTCDate() };
}

function shiftMonths(date: WallDate, by: number): WallDate {
  const shifted = new Date(Date.UTC(date.year, date.month0 + by, date.day));
  return { year: shifted.getUTCFullYear(), month0: shifted.getUTCMonth(), day: shifted.getUTCDate() };
}

/** A wall-clock date as a UTC instant of its midnight (browser or named zone). */
function wallMidnightUtcMs(date: WallDate, timeZone: string | null): number {
  if (timeZone === null || timeZone.trim() === "") {
    return new Date(date.year, date.month0, date.day).getTime(); // browser-local midnight
  }
  return zonedMidnightUtcMs(date.year, date.month0 + 1, date.day, timeZone);
}

/** Half-open `[start, end)` instants (ISO 8601 UTC) for the period containing
 *  `now`, in `timeZone` (null = the browser's local zone).

Boundaries are calendar midnights in that zone, so a user who travels sees
stable "today" edges — same rule as the feed's day grouping. Weeks run
Monday–Sunday (fixed; a configurable start is deferred). All boundary math is
pure wall-clock calendar arithmetic in the zone; instants are derived only at
the end (DST-safe via zonedMidnightUtcMs).
*/
export function periodRange(
  period: Period,
  now = new Date(),
  timeZone: string | null = null,
): PeriodRange {
  const today = zonedDateParts(now, timeZone);

  let start: WallDate;
  if (period === "day") {
    start = today;
  } else if (period === "week") {
    // Weekday of the wall date, via a UTC-midnight Date (deterministic).
    const weekday = new Date(Date.UTC(today.year, today.month0, today.day)).getUTCDay();
    const daysSinceMonday = (weekday + 6) % 7; // getUTCDay(): 0 = Sunday
    start = shiftDays(today, -daysSinceMonday);
  } else if (period === "month") {
    start = { year: today.year, month0: today.month0, day: 1 };
  } else {
    start = { year: today.year, month0: 0, day: 1 };
  }

  const end =
    period === "day"
      ? shiftDays(start, 1)
      : period === "week"
        ? shiftDays(start, 7)
        : period === "month"
          ? shiftMonths(start, 1) // start.day is 1: no end-of-month overflow
          : { year: today.year + 1, month0: 0, day: 1 };

  return {
    start: new Date(wallMidnightUtcMs(start, timeZone)).toISOString(),
    end: new Date(wallMidnightUtcMs(end, timeZone)).toISOString(),
  };
}

/** The remembered selection (localStorage), or the default. */
export function readStoredPeriod(): Period {
  const stored = window.localStorage.getItem(STORAGE_KEY) as Period | null;
  return stored !== null && PERIODS.includes(stored) ? stored : DEFAULT_PERIOD;
}

export function storePeriod(period: Period): void {
  window.localStorage.setItem(STORAGE_KEY, period);
}
