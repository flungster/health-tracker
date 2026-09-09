/** The dashboard: period stats for the current day / week / month / year.

The selection is display-only state (ADR M18): a URL param backed by
localStorage, with the period's [start, end) instants computed client-side in
the local timezone and sent to the summary endpoint. Cards are display-only —
"View all activities" is the single escape hatch to the unfiltered feed.
*/

import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { usePeriodSummary } from "../api/hooks";
import { DistanceTrendChart } from "../components/Charts";
import { Card, EmptyState, ErrorNote, Spinner } from "../components/Ui";
import { capitalize, formatDistance, formatDuration, formatElevation, formatWeight } from "../format";
import { PERIODS, periodLabel, periodRange, readStoredPeriod, storePeriod } from "../periods";
import type { Period } from "../periods";

const segmentBase = "rounded-md px-4 py-2 text-sm font-semibold transition-colors";

export default function DashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawPeriod = searchParams.get("period");
  const period: Period = PERIODS.includes(rawPeriod as Period) ? (rawPeriod as Period) : readStoredPeriod();

  // Keep the URL shareable: record a remembered (or default) period once,
  // without piling up history entries.
  useEffect(() => {
    if (!PERIODS.includes(rawPeriod as Period)) {
      setSearchParams({ period }, { replace: true });
    }
  }, [rawPeriod, period, setSearchParams]);

  function choose(next: Period) {
    storePeriod(next);
    setSearchParams({ period: next }, { replace: true });
  }

  const range = periodRange(period);
  const { data, isPending, isError, error } = usePeriodSummary(range.start, range.end);

  if (isPending) {
    return <Spinner label="Loading your overview…" />;
  }

  if (data === undefined || isError) {
    return <ErrorNote message={error instanceof Error ? error.message : "Could not load your overview."} />;
  }

  const summary = data;
  const units = summary.units;
  const sportChips = Object.entries(summary.activity_count.by_sport_type);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-bold text-ink">{periodLabel(period)}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <Link to="/activities" className="text-sm font-medium text-accent-dark underline hover:text-ink">
            View all activities
          </Link>
          <div className="flex gap-2">
            {PERIODS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => choose(option)}
                className={
                  period === option ? `${segmentBase} bg-accent text-white` : `${segmentBase} border border-line bg-surface text-ink hover:bg-canvas`
                }
              >
                {capitalize(option)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Activities" value={String(summary.activity_count.total)}>
          {sportChips.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {sportChips.map(([sport, count]) => (
                <span key={sport} className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent-dark">
                  {capitalize(sport)}{count > 1 ? ` × ${count}` : ""}
                </span>
              ))}
            </div>
          )}
        </StatTile>
        <StatTile label="Moving time" value={formatDuration(summary.moving_seconds_total)} />
        <StatTile label="Distance" value={formatDistance(summary.distance, units)} />
        <StatTile label="Elevation gain" value={formatElevation(summary.elevation_gain, units)} />
        <StatTile label="Calories" value={summary.calories_kcal !== null ? `${Math.round(summary.calories_kcal)} kcal` : "—"} />
        <StatTile label="Avg heart rate" value={summary.avg_heart_rate_bpm !== null ? `${summary.avg_heart_rate_bpm} bpm` : "—"} />
        <StatTile label="Weight lifted" value={formatWeight(summary.weight_lifted, units)} />
      </dl>

      {period !== "day" && (
        <Card className="p-5">
          <h2 className="text-base font-semibold text-ink">Distance over time</h2>
          {summary.distance_trend.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-muted">No distance recorded in this period.</p>
          ) : (
            <div className="mt-4">
              <DistanceTrendChart
                points={summary.distance_trend}
                units={units}
                granularity={period === "year" ? "month" : "day"}
              />
            </div>
          )}
        </Card>
      )}

      {summary.activity_count.total === 0 && (
        <EmptyState title="Nothing here yet" hint='Switch to a wider period, or head to the feed and upload an activity.' />
      )}
    </div>
  );
}

function StatTile({ label, value, children }: { label: string; value: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <dt className="text-xs uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className="mt-1 truncate text-lg font-semibold text-ink">{value}</dd>
      {children !== undefined && <div>{children}</div>}
    </div>
  );
}
