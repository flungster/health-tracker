/** The linked-duplicates section of a primary activity's detail page (M28).

Linked duplicates are hidden from the feed but kept: each row here can be
promoted to live (the roles swap) or unlinked. Renders nothing while loading
or when there is nothing linked, so ordinary detail pages stay clean. */

import { Link } from "react-router-dom";

import { useLinkDuplicate, useLinkedDuplicates, useUnlinkDuplicate } from "../api/hooks";
import type { ActivitySummaryView } from "../api/types";
import { formatActivityDate, formatClock, formatDuration } from "../format";
import { useTimezone } from "../timezone/context";
import ProviderBadge from "./ProviderBadge";
import { Card, ErrorNote } from "./Ui";

export default function LinkedDuplicatesCard({ activityId }: { activityId: string }) {
  const { timeZone } = useTimezone();
  const { data, isPending } = useLinkedDuplicates(activityId);

  if (isPending || data === undefined) {
    return null;
  }
  if (data.items.length === 0) {
    return null;
  }

  return (
    <Card className="p-5">
      <h2 className="mb-1 text-base font-semibold text-ink">Linked duplicates</h2>
      <p className="mb-4 text-xs text-ink-faint">
        Hidden from your feed, but kept: promote one to make it live instead, or unlink it.
      </p>
      <ul className="divide-y divide-line">
        {data.items.map((item) => (
          <LinkedDuplicateRow key={item.id} primaryId={activityId} item={item} timeZone={timeZone} />
        ))}
      </ul>
    </Card>
  );
}

function LinkedDuplicateRow({
  primaryId,
  item,
  timeZone,
}: {
  primaryId: string;
  item: ActivitySummaryView;
  timeZone: string | null;
}) {
  const promoteMutation = useLinkDuplicate(item.id);
  const unlinkMutation = useUnlinkDuplicate(item.id);

  function handlePromote() {
    if (window.confirm(`Make "${item.name}" the live activity instead?`)) {
      promoteMutation.mutate({ duplicate_of: primaryId, make_primary: true });
    }
  }

  const error = promoteMutation.isError || unlinkMutation.isError;

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0 text-sm">
        <Link to={`/activities/${item.id}`} className="font-medium text-ink hover:text-accent">
          {item.name}
        </Link>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-ink-muted">
          <ProviderBadge provider={item.provider} />
        </div>
      </div>
      <div className="flex items-center gap-2 text-sm">
        <span className="text-xs text-ink-faint" title={item.started_at}>
          {formatActivityDate(item.started_at, timeZone)} ·{" "}
          {formatClock(item.started_at, timeZone)} · {formatDuration(item.duration_seconds)}
        </span>
        <button
          type="button"
          onClick={handlePromote}
          disabled={promoteMutation.isPending || unlinkMutation.isPending}
          className="rounded-md border border-line px-2.5 py-1 text-xs font-semibold text-ink-muted transition-colors hover:bg-line/40 hover:text-ink disabled:opacity-60"
        >
          {promoteMutation.isPending ? "Working…" : "Make this live"}
        </button>
        <button
          type="button"
          onClick={() => unlinkMutation.mutate(undefined)}
          disabled={promoteMutation.isPending || unlinkMutation.isPending}
          className="rounded-md border border-line px-2.5 py-1 text-xs font-semibold text-danger transition-colors hover:bg-danger/5 disabled:opacity-60"
        >
          {unlinkMutation.isPending ? "Working…" : "Unlink"}
        </button>
      </div>
      {error && (
        <p className="w-full">
          <ErrorNote message={promoteMutation.isError ? (promoteMutation.error.message ?? "Something went wrong.") : (unlinkMutation.error?.message ?? "Something went wrong.")} />
        </p>
      )}
    </li>
  );
}
