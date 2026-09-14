/** Charts (recharts): activity detail + the dashboard distance trend. */

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

import type { HrZoneView, TrackpointView, Units } from "../api/types";
import { clockFromSeconds, formatDistance } from "../format";
import { chartPalette, tooltipStyle } from "../theme/chartColors";
import { useTheme } from "../theme/context";

type HeartRateChartProps = {
  trackpoints: TrackpointView[];
  startedAt: string;
};

export function HeartRateChart({ trackpoints, startedAt }: HeartRateChartProps) {
  const palette = chartPalette(useTheme().dark);
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
          <CartesianGrid stroke={palette.grid} strokeDasharray="3 3" />
          <XAxis dataKey="time" tick={{ fontSize: 11, fill: palette.tick }} />
          <YAxis
            tick={{ fontSize: 11, fill: palette.tick }}
            domain={["dataMin - 5", "dataMax + 5"]}
          />
          <Tooltip
            contentStyle={{ ...tooltipStyle(palette) }}
            formatter={(value) => [`${value} bpm`, "Heart rate"]}
          />
          <Line
            type="monotone"
            dataKey="bpm"
            stroke={palette.accent}
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

export function HrZonesChart({ zones }: { zones: HrZoneView }) {
  const palette = chartPalette(useTheme().dark);
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
          <CartesianGrid stroke={palette.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: palette.tick }} />
          <YAxis tick={{ fontSize: 11, fill: palette.tick }} />
          <Tooltip
            contentStyle={{ ...tooltipStyle(palette) }}
            formatter={(value, _name, item) => [
              `${value} s (${(item?.payload as { percent: number } | undefined)?.percent ?? 0}%)`,
              "Time",
            ]}
          />
          <Bar dataKey="seconds" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((entry, index) => (
              <Cell key={entry.label} fill={palette.zoneColors[index]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

type DistanceTrendChartProps = {
  /** Buckets in the caller's display system (already converted by the API). */
  points: { start: string; value: number }[];
  units: Units;
  /** Day buckets (week/month views) or month buckets (year view). */
  granularity: "day" | "month";
};

function dayTick(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function monthTick(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short" });
}

/** Distance over time for the dashboard (bars per day or month). */
export function DistanceTrendChart({ points, units, granularity }: DistanceTrendChartProps) {
  const palette = chartPalette(useTheme().dark);
  const data = points.map((point) => ({
    start: point.start,
    value: point.value,
    label: granularity === "day" ? dayTick(point.start) : monthTick(point.start),
  }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
          <CartesianGrid stroke={palette.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: palette.tick }} minTickGap={12} />
          <YAxis tick={{ fontSize: 11, fill: palette.tick }} />
          <Tooltip
            contentStyle={{ ...tooltipStyle(palette) }}
            cursor={{ fill: palette.cursorFill }}
            labelFormatter={(label, items) => {
              const iso = (items?.[0]?.payload as { start: string } | undefined)?.start;
              if (iso === undefined) {
                return String(label);
              }
              const date = new Date(iso);
              return granularity === "day"
                ? date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
                : date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
            }}
            formatter={(value) => [formatDistance(Number(value), units), "Distance"]}
          />
          <Bar dataKey="value" fill={palette.accent} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
