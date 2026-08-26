/** Charts for the activity detail page (recharts). */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HrZoneView, TrackpointView } from "../api/types";
import { clockFromSeconds } from "../format";

type HeartRateChartProps = {
  trackpoints: TrackpointView[];
  startedAt: string;
};

export function HeartRateChart({ trackpoints, startedAt }: HeartRateChartProps) {
  const start = new Date(startedAt).getTime();
  const data = trackpoints
    .filter((point) => point.heart_rate_bpm !== null && point.recorded_at !== null)
    .map((point) => ({
      time: clockFromSeconds(
        Math.round((new Date(point.recorded_at as string).getTime() - start) / 1000),
      ),
      bpm: point.heart_rate_bpm as number,
    }));
  if (data.length < 2) {
    return (
      <p className="py-8 text-center text-sm text-ink-muted">
        No heart-rate data recorded.
      </p>
    );
  }
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="#e3e1dc" strokeDasharray="3 3" />
          <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#6f6d68" }} />
          <YAxis
            tick={{ fontSize: 11, fill: "#6f6d68" }}
            domain={["dataMin - 5", "dataMax + 5"]}
          />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #e3e1dc", fontSize: 12 }}
            formatter={(value) => [`${value} bpm`, "Heart rate"]}
          />
          <Line
            type="monotone"
            dataKey="bpm"
            stroke="#2f6f6a"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const ZONE_LABELS = [
  "Zone 1",
  "Zone 2",
  "Zone 3",
  "Zone 4",
  "Zone 5",
] as const;

const ZONE_COLORS = ["#a8c4c1", "#7fa8a4", "#5d948f", "#3d7c76", "#2f6f6a"] as const;

export function HrZonesChart({ zones }: { zones: HrZoneView }) {
  const values = [
    zones.zone_1_seconds,
    zones.zone_2_seconds,
    zones.zone_3_seconds,
    zones.zone_4_seconds,
    zones.zone_5_seconds,
  ];
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total <= 0) {
    return (
      <p className="py-8 text-center text-sm text-ink-muted">
        No heart-rate data recorded.
      </p>
    );
  }
  const data = ZONE_LABELS.map((label, index) => ({
    label,
    seconds: values[index],
    percent: Math.round((values[index] / total) * 100),
  }));
  return (
    <div className="h-52 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="#e3e1dc" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#6f6d68" }} />
          <YAxis tick={{ fontSize: 11, fill: "#6f6d68" }} />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #e3e1dc", fontSize: 12 }}
            formatter={(value, _name, item) => [
              `${value} s (${(item?.payload as { percent: number } | undefined)?.percent ?? 0}%)`,
              "Time",
            ]}
          />
          <Bar dataKey="seconds" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((entry, index) => (
              <Cell key={entry.label} fill={ZONE_COLORS[index]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
