/** The activity feed: day-grouped, newest first, with load-more. */

import { useMemo } from "react";
import { Link } from "react-router-dom";

import { useActivitiesInfinite } from "../api/hooks";
import type { ActivitySummaryView } from "../api/types";
import ActivityCard from "../components/ActivityCard";
import { EmptyState, ErrorNote, Spinner } from "../components/Ui";
import { dayKey, dayLabel } from "../format";

type DayGroup = {
  key: string;
  label: string;
  activities: ActivitySummaryView[];
};

export default function ActivitiesPage() {
  const {
    data,
    isPending,
    isError,
    error,
    fetchNextPage,
    isFetchingNextPage,
    hasNextPage,
  } = useActivitiesInfinite();

  const groups = useMemo<DayGroup[]>(() => {
    const all = (data?.pages ?? []).flatMap((page) => page.items);
    const byDay = new Map<string, ActivitySummaryView[]>();
    for (const activity of all) {
      const key = dayKey(activity.started_at);
      const bucket = byDay.get(key);
      if (bucket === undefined) {
        byDay.set(key, [activity]);
      } else {
        bucket.push(activity);
      }
    }
    // Keys are ISO dates, so sorting desc = newest day first.
    return [...byDay.entries()]
      .sort((a, b) => (a[0] < b[0] ? 1 : -1))
      .map(([key, activities]) => ({ key, label: dayLabel(key), activities }));
  }, [data]);

  if (isPending) {
    return <Spinner label="Loading your activities…" />;
  }

  if (isError) {
    return <ErrorNote message={error instanceof Error ? error.message : "Could not load activities."} />;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-ink">Activities</h1>
        <Link
          to="/upload"
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark"
        >
          + Upload activity
        </Link>
      </div>

      {groups.length === 0 ? (
        <EmptyState
          title="No activities yet"
          hint="Import a GPX, TCX or FIT file to get started."
        />
      ) : (
        <>
          {groups.map((group) => (
            <section key={group.key} className="space-y-2">
              <h2 className="px-1 text-sm font-semibold text-ink-muted">{group.label}</h2>
              <div className="space-y-2">
                {group.activities.map((activity) => (
                  <ActivityCard key={activity.id} activity={activity} />
                ))}
              </div>
            </section>
          ))}

          {hasNextPage === true && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
                className="rounded-md border border-line bg-surface px-5 py-2 text-sm font-medium text-ink transition-colors hover:border-ink-faint disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isFetchingNextPage ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
