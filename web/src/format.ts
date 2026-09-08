/** Display formatting helpers (distances, durations, paces, dates). */

import type { Units } from "./api/types";

/** Distance in the display system: m/km for metric, miles (1 decimal) otherwise. */
export function formatDistance(value: number | null, units: Units = "metric"): string {
  if (value === null) {
    return "—";
  }
  if (units === "imperial") {
    return `${value.toFixed(1)} mi`;
  }
  if (value < 1000) {
    return `${Math.round(value)} m`;
  }
  return `${(value / 1000).toFixed(2)} km`;
}

/** Elevation in the display system: meters for metric, whole feet otherwise. */
export function formatElevation(value: number | null, units: Units = "metric"): string {
  if (value === null) {
    return "—";
  }
  if (units === "imperial") {
    return `${Math.round(value).toLocaleString()} ft`;
  }
  // Metric elevation has always read like a distance ("88 m", "1.23 km").
  return formatDistance(value);
}

/** Weight in the display system: kg for metric, whole lb otherwise. */
export function formatWeight(value: number | null, units: Units = "metric"): string {
  if (value === null) {
    return "—";
  }
  if (units === "imperial") {
    return `${Math.round(value).toLocaleString()} lb`;
  }
  return `${Math.round(value)} kg`;
}

/** Pace suffix for the display system ("/km" or "/mi"). */
export function paceSuffix(units: Units = "metric"): string {
  return units === "imperial" ? "/mi" : "/km";
}

export function formatDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds === null || totalSeconds === undefined) {
    return "—";
  }
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.round(totalSeconds % 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

/** Pace in the "5'32\"" style, from seconds per unit. */
export function formatPace(secondsPerUnit: number | null | undefined): string {
  if (secondsPerUnit === null || secondsPerUnit === undefined) {
    return "—";
  }
  const minutes = Math.floor(secondsPerUnit / 60);
  const seconds = Math.round(secondsPerUnit % 60);
  return `${minutes}'${String(seconds).padStart(2, "0")}"`;
}

/** Local date key (YYYY-MM-DD) for grouping the feed by day. */
export function dayKey(iso: string): string {
  const date = new Date(iso);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Human label for a day key: Today, Yesterday, or the full date. */
export function dayLabel(key: string): string {
  const today = new Date();
  const todayKey = dayKey(today.toISOString());
  if (key === todayKey) {
    return "Today";
  }
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (key === dayKey(yesterday.toISOString())) {
    return "Yesterday";
  }
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function formatActivityDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatClock(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** Elapsed mm:ss for chart axes, relative to a start timestamp. */
export function clockFromSeconds(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Local date key (YYYY-MM-DD) for N days before today. */
export function dateDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}
