/** Sport-specific metric cards for the activity detail page. */

import type {
  CyclingMetricsView,
  RowingMetricsView,
  RunningMetricsView,
  StrengthMetricsView,
  WalkingMetricsView,
} from "../api/types";
import { formatDistance, formatPace, formatWeight, paceSuffix } from "../format";
import { useUnits } from "../units/context";
import { Card } from "../components/Ui";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-canvas px-3 py-2">
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-ink">{value}</dd>
    </div>
  );
}

export function RunningDetail({ running }: { running: RunningMetricsView }) {
  const { units } = useUnits();
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-ink">Running</h2>
      <dl className="mt-3 grid grid-cols-3 gap-3">
        <Metric label="Avg pace" value={formatPace(running.avg_pace_seconds) + " " + paceSuffix(units)} />
        <Metric label="Best pace" value={formatPace(running.min_pace_seconds) + " " + paceSuffix(units)} />
        <Metric label="Slowest pace" value={formatPace(running.max_pace_seconds) + " " + paceSuffix(units)} />
      </dl>
    </Card>
  );
}

export function WalkingDetail({ walking, distance }: { walking: WalkingMetricsView; distance: number | null }) {
  const { units } = useUnits();
  const paceValue =
    walking.avg_pace_seconds !== null ? formatPace(walking.avg_pace_seconds) + " " + paceSuffix(units) : "—";
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-ink">Walking</h2>
      <dl className="mt-3 grid grid-cols-2 gap-3">
        <Metric label="Avg pace" value={paceValue} />
        <Metric label="Distance" value={formatDistance(distance, units)} />
      </dl>
    </Card>
  );
}

export function CyclingDetail({ cycling }: { cycling: CyclingMetricsView }) {
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-ink">Cycling</h2>
      <dl className="mt-3 grid grid-cols-2 gap-3">
        <Metric
          label="Avg power"
          value={cycling.power_avg_w !== null ? `${Math.round(cycling.power_avg_w)} W` : "—"}
        />
        <Metric
          label="Max power"
          value={cycling.power_max_w !== null ? `${Math.round(cycling.power_max_w)} W` : "—"}
        />
      </dl>
    </Card>
  );
}

export function RowingDetail({ rowing, distance }: { rowing: RowingMetricsView; distance: number | null }) {
  const { units } = useUnits();
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-ink">Rowing</h2>
      <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Metric
          label="Avg stroke rate"
          value={rowing.stroke_rate_avg_spm !== null ? `${Math.round(rowing.stroke_rate_avg_spm)} spm` : "—"}
        />
        <Metric
          label="Min stroke rate"
          value={rowing.stroke_rate_min_spm !== null ? `${Math.round(rowing.stroke_rate_min_spm)} spm` : "—"}
        />
        <Metric
          label="Max stroke rate"
          value={rowing.stroke_rate_max_spm !== null ? `${Math.round(rowing.stroke_rate_max_spm)} spm` : "—"}
        />
        <Metric
          label="500 m split"
          value={rowing.split_500m_seconds !== null ? formatPace(rowing.split_500m_seconds) : "—"}
        />
        <Metric label="Distance" value={formatDistance(distance, units)} />
      </dl>
    </Card>
  );
}

export function StrengthDetail({ strength }: { strength: StrengthMetricsView }) {
  const { units } = useUnits();
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-ink">Strength</h2>
      <dl className="mt-3 grid grid-cols-3 gap-3">
        <Metric label="Exercises" value={`${strength.total_exercises}`} />
        <Metric label="Sets" value={`${strength.total_sets}`} />
        <Metric label="Total volume" value={formatWeight(strength.total_weight, units)} />
      </dl>
    </Card>
  );
}

/** Fallback for sports without a dedicated view. */
export function GenericDetail({ sportType }: { sportType: string }) {
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-ink">{sportType.charAt(0).toUpperCase() + sportType.slice(1)}</h2>
      <p className="mt-2 text-sm text-ink-muted">
        No sport-specific metrics available for this activity.
      </p>
    </Card>
  );
}
