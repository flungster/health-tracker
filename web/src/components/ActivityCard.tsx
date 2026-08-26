/** One activity row in the feed. */

import { Link } from "react-router-dom";

import type { ActivitySummaryView } from "../api/types";
import { formatActivityDate, formatClock, formatDistance, formatDuration } from "../format";
import SportBadge from "./SportBadge";
import { Card } from "./Ui";

export default function ActivityCard({ activity }: { activity: ActivitySummaryView }) {
  return (
    <Card className="px-5 py-4 transition-shadow hover:shadow-sm">
      <Link to={`/activities/${activity.id}`} className="block">
        <div className="flex items-center gap-3">
          <SportBadge sportType={activity.sport_type} />
          <span className="truncate text-sm font-semibold text-ink">
            {activity.name}
          </span>
          <span className="ml-auto shrink-0 text-xs text-ink-faint">
            {formatActivityDate(activity.started_at)} · {formatClock(activity.started_at)}
          </span>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-muted">
          <span>
            {formatDistance(activity.distance_m)}
          </span>
          <span>{formatDuration(activity.duration_seconds)}</span>
          {activity.heart_rate_avg_bpm !== null && (
            <span>{activity.heart_rate_avg_bpm} bpm avg</span>
          )}
          {activity.calories_kcal !== null && <span>{Math.round(activity.calories_kcal)} kcal</span>}
        </div>
      </Link>
    </Card>
  );
}
