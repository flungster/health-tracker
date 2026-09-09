/** Dashboard period model: the four fixed segments and their [start, end) ranges.

The selection is display-only state (ADR M18): the client computes half-open
UTC instants in its *local* timezone (consistent with the feed's Today /
Yesterday grouping) and sends them to the summary endpoint. No server state.
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

/** Half-open `[start, end)` instants (ISO 8601 UTC) for the period containing `now`.

Boundaries are local calendar boundaries (midnights in the browser's timezone),
so a user who travels sees stable "today" edges — same rule as the feed's day
grouping. Weeks run Monday–Sunday (fixed; a configurable start is deferred).
*/
export function periodRange(period: Period, now = new Date()): PeriodRange {
  let start: Date;
  if (period === "day") {
    start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else if (period === "week") {
    // getDay(): 0 = Sunday … 6 = Saturday → days since the Monday on/after…
    const daysSinceMonday = (now.getDay() + 6) % 7;
    start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - daysSinceMonday);
  } else if (period === "month") {
    start = new Date(now.getFullYear(), now.getMonth(), 1);
  } else {
    start = new Date(now.getFullYear(), 0, 1);
  }

  const end: Date =
    period === "day"
      ? new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1)
      : period === "week"
        ? new Date(start.getFullYear(), start.getMonth(), start.getDate() + 7)
        : period === "month"
          ? new Date(start.getFullYear(), start.getMonth() + 1, 1)
          : new Date(start.getFullYear() + 1, 0, 1);

  return { start: start.toISOString(), end: end.toISOString() };
}

/** The remembered selection (localStorage), or the default. */
export function readStoredPeriod(): Period {
  const stored = window.localStorage.getItem(STORAGE_KEY) as Period | null;
  return stored !== null && PERIODS.includes(stored) ? stored : DEFAULT_PERIOD;
}

export function storePeriod(period: Period): void {
  window.localStorage.setItem(STORAGE_KEY, period);
}
