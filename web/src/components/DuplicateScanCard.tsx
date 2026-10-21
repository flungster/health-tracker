/** Library-wide duplicate scan (M29b): one opt-in action, then a report of the
 *  groups that look like the same workout. The scan itself never links anything —
 *  per group, pick which activity to keep and the rest are linked as duplicates of
 *  it (M28's endpoints, which invalidate the feed and detail caches). Mirrors
 *  WeatherCard's opt-in shape: an action, a loading state, then the result. */

import { useState } from "react";
import { Link } from "react-router-dom";

import { useDuplicateScan, useLinkDuplicateGroup } from "../api/hooks";
import type { ActivitySummaryView, DuplicateGroupView, DuplicateScanView, Units } from "../api/types";
import { formatActivityDate, formatClock, formatDistance, formatDuration } from "../format";
import { useTimezone } from "../timezone/context";
import ProviderBadge from "./ProviderBadge";
import SportBadge from "./SportBadge";
import { Card, ErrorNote, Spinner } from "./Ui";

/** A stable per-group key (member ids joined): unique across groups, so the
 *  radio names and React keys stay unambiguous. */
function groupKey(activities: ActivitySummaryView[]): string {
  return activities.map((activity) => activity.id).join("|");
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

const secondaryButton =
  "rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-muted transition-colors hover:bg-line/40 hover:text-ink disabled:opacity-60";

export default function DuplicateScanCard() {
  const scanMutation = useDuplicateScan();
  // The last successful report (kept, so a failed re-scan does not wipe it).
  const [result, setResult] = useState<DuplicateScanView | null>(null);

  function handleScanned(data: DuplicateScanView) {
    setResult(data);
  }

  if (scanMutation.isPending) {
    return (
      <Card className="p-5">
        <Spinner label="Scanning your library…" />
      </Card>
    );
  }

  if (result === null) {
    return (
      <Card className="p-5">
        {scanMutation.isError ? (
          <>
            <ErrorNote message={messageOf(scanMutation.error, "Could not scan for duplicates.")} />
            <button
              type="button"
              onClick={() => scanMutation.mutate(undefined, { onSuccess: handleScanned })}
              className={`${secondaryButton} mt-3`}
            >
              Try again
            </button>
          </>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
            <p className="max-w-prose text-sm text-ink-muted">
              Check your whole library for the same workout imported from more than one source. The scan only
              reports — you pick what to keep; nothing is linked automatically.
            </p>
            <button
              type="button"
              onClick={() => scanMutation.mutate(undefined, { onSuccess: handleScanned })}
              className={secondaryButton}
            >
              Scan library for duplicates
            </button>
          </div>
        )}
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Duplicate scan</h2>
          <p className="mt-0.5 text-xs text-ink-faint">Groups of activities that look like the same workout.</p>
        </div>
        <button
          type="button"
          onClick={() => scanMutation.mutate(undefined, { onSuccess: handleScanned })}
          className={secondaryButton}
        >
          Scan again
        </button>
      </div>

      {scanMutation.isError && (
        <div className="mt-4">
          <ErrorNote message={messageOf(scanMutation.error, "Could not scan for duplicates.")} />
        </div>
      )}

      <div className="mt-4">
        {result.groups.length === 0 ? (
          <p className="text-sm text-ink-muted">No duplicate activities found — your library looks clean.</p>
        ) : (
          <div className="space-y-6">
            {result.groups.map((group) => (
              <ScanGroup key={groupKey(group.activities)} groupActivities={group} units={result.units} />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

type ScanGroupProps = { groupActivities: DuplicateGroupView; units: Units };

/** One scan cluster. The first member (earliest start) is the natural primary to
 *  keep, so it starts preselected; linking every other member uses M28's endpoint
 *  per activity (idempotent — a failed batch can be retried as-is). */
function ScanGroup({ groupActivities, units }: ScanGroupProps) {
  const activities = groupActivities.activities;
  const { timeZone } = useTimezone();

  // The first member (earliest start) is the natural primary to keep: preselect it.
  const [keepId, setKeepId] = useState(activities[0]?.id ?? "");
  // The kept activity's name, once every other member has been linked.
  const [resolvedName, setResolvedName] = useState<string | null>(null);

  const linkMutation = useLinkDuplicateGroup(keepId);
  const keptName = activities.find((activity) => activity.id === keepId)?.name ?? "";
  // The members that would be linked if the user confirms: everyone but the kept one.
  const memberIds = activities.filter((activity) => activity.id !== keepId).map((activity) => activity.id);
  const othersCount = memberIds.length;

  function handleLink() {
    linkMutation.mutate(memberIds, { onSuccess: () => setResolvedName(keptName) });
  }

  return (
    <section>
      <p className="text-sm font-medium text-ink">These {activities.length} activities look like the same workout</p>
      <p className="mb-3 mt-0.5 text-xs text-ink-faint">
        Pick which one to keep; the others are linked as duplicates (hidden from your feed, kept).
      </p>

      <ul className="divide-y divide-line">
        {activities.map((activity) => (
          <li key={activity.id} className="py-3 first:pt-0 last:pb-0">
            <label
              className={`flex flex-wrap items-center gap-x-3 ${resolvedName === null ? "cursor-pointer" : ""}`}
            >
              <input
                type="radio"
                name={`keep-${groupKey(activities)}`}
                value={activity.id}
                checked={activity.id === keepId}
                disabled={resolvedName !== null || linkMutation.isPending}
                onChange={() => setKeepId(activity.id)}
              />
              <span className="min-w-0 flex-1">
                <Link to={`/activities/${activity.id}`} className="block truncate text-sm font-medium text-ink hover:text-accent">
                  {activity.name}
                </Link>
                <span className="mt-0.5 flex items-center gap-2">
                  <SportBadge sportType={activity.sport_type} />
                  <ProviderBadge provider={activity.provider} />
                </span>
              </span>
              <span className="shrink-0 text-right">
                <span className="block text-xs text-ink-faint" title={activity.started_at}>
                  {formatActivityDate(activity.started_at, timeZone)} ·{" "}
                  {formatClock(activity.started_at, timeZone)}
                </span>
                <span className="mt-0.5 block text-xs text-ink-muted">
                  {formatDistance(activity.distance, units)} · {formatDuration(activity.duration_seconds)}
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>

      {resolvedName === null ? (
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={handleLink}
            disabled={linkMutation.isPending}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
          >
            {linkMutation.isPending ? "Linking…" : `Link ${othersCount} as duplicate${othersCount === 1 ? "" : "s"}`}
          </button>
          {linkMutation.isError && (
            <span className="min-w-0 flex-1">
              <ErrorNote message={messageOf(linkMutation.error, "Could not link the duplicates.")} />
            </span>
          )}
        </div>
      ) : (
        <p className="mt-3 text-sm text-ink-muted">
          Linked {othersCount} as duplicate{othersCount === 1 ? "" : "s"} of{" "}
          <Link to={`/activities/${keepId}`} className="font-medium text-accent hover:underline">
            {resolvedName}
          </Link>
          .
        </p>
      )}
    </section>
  );
}
