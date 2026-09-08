/** Per-unit split table (rows of the caller's system, from `split_type`). */

import type { SplitView } from "../api/types";
import { formatDuration, formatPace } from "../format";
import { Card } from "./Ui";

export default function SplitsTable({ splits }: { splits: SplitView[] }) {
  if (splits.length === 0) {
    return null;
  }
  // The API returns only the caller's system (km rows for metric, mi otherwise).
  const unit = splits[0].split_type;
  const hasCadence = splits.some((split) => split.cadence_avg_rpm !== null);
  const hasHr = splits.some((split) => split.heart_rate_avg_bpm !== null);

  return (
    <Card className="space-y-6 p-5">
      <h2 className="text-base font-semibold text-ink">Splits</h2>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-ink">
          Per {unit === "km" ? "kilometre" : "mile"}
        </h3>
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-canvas text-left text-xs uppercase tracking-wide text-ink-faint">
                <th className="px-3 py-2 font-medium">#{unit}</th>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Pace</th>
                {hasHr && <th className="px-3 py-2 font-medium">Avg HR</th>}
                {hasCadence && <th className="px-3 py-2 font-medium">Cadence</th>}
              </tr>
            </thead>
            <tbody>
              {splits.map((split) => (
                <tr key={split.split_index} className="border-b border-line last:border-b-0">
                  <td className="px-3 py-2 text-ink-muted">{split.split_index}</td>
                  <td className="px-3 py-2 text-ink">
                    {formatDuration(split.duration_seconds)}
                  </td>
                  <td className="px-3 py-2 text-ink">{formatPace(split.pace_seconds)}</td>
                  {hasHr && (
                    <td className="px-3 py-2 text-ink-muted">
                      {split.heart_rate_avg_bpm !== null ? `${split.heart_rate_avg_bpm} bpm` : "—"}
                    </td>
                  )}
                  {hasCadence && (
                    <td className="px-3 py-2 text-ink-muted">
                      {split.cadence_avg_rpm !== null ? `${split.cadence_avg_rpm} rpm` : "—"}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}
