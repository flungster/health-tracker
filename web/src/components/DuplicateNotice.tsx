/** Banner for an activity that is a linked duplicate (M28): this row stays
 *  stored and reachable, but hidden from the feed while linked. */

import { Link } from "react-router-dom";

import { useLinkDuplicate, useUnlinkDuplicate } from "../api/hooks";
import { Card, ErrorNote } from "./Ui";

export default function DuplicateNotice({
  activityId,
  primaryId,
}: {
  activityId: string;
  primaryId: string;
}) {
  const promoteMutation = useLinkDuplicate(activityId);
  const unlinkMutation = useUnlinkDuplicate(activityId);

  function handlePromote() {
    if (window.confirm("Make this activity the live one instead of the linked primary?")) {
      promoteMutation.mutate({ duplicate_of: primaryId, make_primary: true });
    }
  }

  function handleUnlink() {
    unlinkMutation.mutate(undefined);
  }

  const error = promoteMutation.isError || unlinkMutation.isError;

  return (
    <Card className="border-accent/40 bg-surface p-5">
      <p className="text-sm text-ink-muted">
        This activity is linked as a duplicate of another one, so it does not appear in your feed.{" "}
        <Link to={`/activities/${primaryId}`} className="text-accent underline">
          Open the live activity
        </Link>
      </p>
      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={handlePromote}
          disabled={promoteMutation.isPending || unlinkMutation.isPending}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
        >
          {promoteMutation.isPending ? "Working…" : "Make this one live"}
        </button>
        <button
          type="button"
          onClick={handleUnlink}
          disabled={promoteMutation.isPending || unlinkMutation.isPending}
          className="rounded-md border border-line px-3 py-1.5 text-sm font-semibold text-ink-muted transition-colors hover:bg-line/40 hover:text-ink disabled:opacity-60"
        >
          {unlinkMutation.isPending ? "Working…" : "Unlink"}
        </button>
      </div>
      {error && (
        <div className="mt-3">
          <ErrorNote message={promoteMutation.isError ? (promoteMutation.error.message ?? "Something went wrong.") : (unlinkMutation.error?.message ?? "Something went wrong.")} />
        </div>
      )}
    </Card>
  );
}
