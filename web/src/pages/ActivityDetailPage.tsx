/** Single activity: header, stats, map, splits, HR, sport metrics, delete. */

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useActivity, useDeleteActivity, useTrackpoints, useUpdateActivity } from "../api/hooks";
import { HeartRateChart, HrZonesChart } from "../components/Charts";
import RouteMap from "../components/RouteMap";
import SportBadge from "../components/SportBadge";
import SplitsTable from "../components/SplitsTable";
import StatGrid from "../components/StatGrid";
import { Card, ErrorNote, Spinner } from "../components/Ui";
import {
  CyclingDetail,
  GenericDetail,
  RowingDetail,
  RunningDetail,
  StrengthDetail,
} from "../features/SportDetails";
import {
  capitalize,
  formatActivityDate,
  formatClock,
  formatDistance,
  formatDuration,
  formatPace,
} from "../format";

export default function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const activityId = id ?? "";

  const { data: activity, isPending, isError, error } = useActivity(activityId);
  const { data: trackpointsData } = useTrackpoints(activityId);
  const updateMutation = useUpdateActivity(activityId);
  const deleteMutation = useDeleteActivity();

  const [editingName, setEditingName] = useState(false);
  const [draftName, setDraftName] = useState("");

  if (isPending) {
    return <Spinner label="Loading activity…" />;
  }

  if (isError || activity === undefined) {
    return (
      <ErrorNote
        message={error instanceof Error ? error.message : "Activity not found."}
      />
    );
  }

  const trackpoints = trackpointsData?.items ?? [];
  const hasGps = trackpoints.some((point) => point.lat !== null && point.lon !== null);

  function startRename() {
    if (activity !== undefined) {
      setDraftName(activity.name);
    }
    setEditingName(true);
  }

  function commitRename() {
    const trimmed = draftName.trim();
    if (trimmed !== "" && trimmed !== activity?.name) {
      updateMutation.mutate({ name: trimmed, description: null, sport_type: null });
    }
    setEditingName(false);
  }

  function handleDelete() {
    if (window.confirm("Delete this activity? This cannot be undone.")) {
      deleteMutation.mutate(activityId, {
        onSuccess: () => navigate("/", { replace: true }),
      });
    }
  }

  const avgPace = activity.running?.avg_pace_s_per_km ?? null;
  const stats = [
    { label: "Distance", value: formatDistance(activity.distance_m) },
    { label: "Time", value: formatDuration(activity.duration_seconds) },
    {
      label: "Moving time",
      value: formatDuration(activity.moving_seconds),
    },
    {
      label: "Elev gain",
      value: formatDistance(activity.elevation_gain_m),
    },
    {
      label: "Calories",
      value: activity.calories_kcal !== null ? `${Math.round(activity.calories_kcal)} kcal` : "—",
    },
    {
      label: "Avg pace",
      value: avgPace !== null ? `${formatPace(avgPace)}/km` : "—",
    },
    {
      label: "Avg HR",
      value: activity.heart_rate_avg_bpm !== null ? `${activity.heart_rate_avg_bpm} bpm` : "—",
    },
    {
      label: "Max HR",
      value: activity.heart_rate_max_bpm !== null ? `${activity.heart_rate_max_bpm} bpm` : "—",
    },
    {
      label: "Avg cadence",
      value: activity.cadence_avg_rpm !== null ? `${activity.cadence_avg_rpm} rpm` : "—",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-ink-muted hover:text-ink">
          ← Back to activities
        </Link>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <SportBadge sportType={activity.sport_type} />
            {editingName ? (
              <input
                autoFocus
                value={draftName}
                onChange={(event) => setDraftName(event.target.value)}
                onBlur={commitRename}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    commitRename();
                  } else if (event.key === "Escape") {
                    setEditingName(false);
                  }
                }}
                className="rounded-md border border-line bg-surface px-2 py-1 text-xl font-bold text-ink outline-none focus:border-accent"
              />
            ) : (
              <button
                type="button"
                onClick={startRename}
                title="Rename"
                className="truncate text-xl font-bold text-ink hover:text-accent"
              >
                {activity.name}
              </button>
            )}
          </div>
          <p className="mt-1 text-sm text-ink-muted">
            {formatActivityDate(activity.started_at)} at {formatClock(activity.started_at)}
          </p>
          {activity.description !== null && activity.description !== "" && (
            <p className="mt-2 text-sm text-ink-muted">{activity.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="rounded-md border border-danger/30 px-3 py-1.5 text-sm text-danger transition-colors hover:bg-danger/5 disabled:opacity-60"
        >
          {deleteMutation.isPending ? "Deleting…" : "Delete"}
        </button>
      </div>

      <StatGrid stats={stats} />

      {hasGps && (
        <Card className="p-5">
          <h2 className="mb-4 text-base font-semibold text-ink">Route</h2>
          <RouteMap trackpoints={trackpoints} />
        </Card>
      )}

      <SplitsTable splits={activity.splits} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="mb-4 text-base font-semibold text-ink">Heart rate</h2>
          <HeartRateChart trackpoints={trackpoints} startedAt={activity.started_at} />
        </Card>
        <Card className="p-5">
          <h2 className="mb-4 text-base font-semibold text-ink">
            Time in heart-rate zones
          </h2>
          {activity.heart_rate_zones !== null ? (
            <HrZonesChart zones={activity.heart_rate_zones} />
          ) : (
            <p className="py-8 text-center text-sm text-ink-muted">
              No heart-rate data recorded.
            </p>
          )}
        </Card>
      </div>

      {activity.running !== null && <RunningDetail running={activity.running} />}
      {activity.cycling !== null && <CyclingDetail cycling={activity.cycling} />}
      {activity.rowing !== null && <RowingDetail rowing={activity.rowing} />}
      {activity.strength !== null && <StrengthDetail strength={activity.strength} />}
      {activity.running === null &&
        activity.cycling === null &&
        activity.rowing === null &&
        activity.strength === null &&
        activity.sport_type !== "strength" && <GenericDetail sportType={activity.sport_type} />}

      <p className="text-xs text-ink-faint">
        Imported from {capitalize(activity.source_format)}
        {activity.original_filename !== null && <> · {activity.original_filename}</>}
      </p>
    </div>
  );
}
