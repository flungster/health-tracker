/** Opt-in weather card for an outdoor activity (M24): fetch button, then the
 *  cached Open-Meteo snapshot — start/end conditions plus a temperature-over-
 *  time line for longer efforts. Strictly on-demand: nothing is fetched until
 *  the user clicks; afterwards the snapshot comes from the server-side cache.
 */

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useActivityWeather, useFetchWeather } from "../api/hooks";
import type { ActivityWeatherView, WeatherPointView } from "../api/types";
import { clockFromSeconds, formatClock } from "../format";
import { useTimezone } from "../timezone/context";
import { ErrorNote, Spinner } from "./Ui";

/** WMO weather interpretation codes -> short labels (the full set Open-Meteo
 *  returns for historical hours). Unknown codes fall back to the raw code. */
const WMO_LABELS: Record<number, string> = {
  0: "Clear sky",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Depositing rime fog",
  51: "Light drizzle",
  53: "Drizzle",
  55: "Dense drizzle",
  56: "Light freezing drizzle",
  57: "Freezing drizzle",
  61: "Light rain",
  63: "Rain",
  65: "Heavy rain",
  66: "Light freezing rain",
  67: "Freezing rain",
  71: "Light snowfall",
  73: "Snowfall",
  75: "Heavy snowfall",
  77: "Snow grains",
  80: "Light rain showers",
  81: "Rain showers",
  82: "Violent rain showers",
  85: "Light snow showers",
  86: "Snow showers",
  95: "Thunderstorm",
  96: "Thunderstorm with hail",
  99: "Thunderstorm with heavy hail",
};

/** The display label for a WMO code (or the raw code when unrecognized). */
export function weatherLabel(code: number | null): string {
  if (code === null) {
    return "Unknown";
  }
  const label = WMO_LABELS[code];
  return label !== undefined ? label : `Code ${code}`;
}

/** The snapshot hour closest to an instant (for start/end conditions). */
function nearestPoint(points: WeatherPointView[], isoInstant: string): WeatherPointView {
  const target = new Date(isoInstant).getTime();
  let best = points[0];
  for (const point of points) {
    if (Math.abs(new Date(point.time).getTime() - target) < Math.abs(new Date(best.time).getTime() - target)) {
      best = point;
    }
  }
  return best;
}

/** "21°" style temperatures (nulls render as an em dash, like the rest of the UI). */
function temp(celsius: number | null): string {
  return celsius === null ? "—" : `${Math.round(celsius)}°`;
}

type ConditionChipProps = { label: string; point: WeatherPointView };

function ConditionChip({ label, point }: ConditionChipProps) {
  return (
    <div className="rounded-md border border-line bg-canvas px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">
        {weatherLabel(point.weather_code)} · {temp(point.temperature_c)}
      </p>
      <div className="mt-2 grid grid-cols-3 gap-x-4 text-xs text-ink-muted">
        <span>Feels {temp(point.apparent_temperature_c)}</span>
        <span>Humidity {point.relative_humidity_pct === null ? "—" : `${Math.round(point.relative_humidity_pct)}%`}</span>
        <span>Dew point {temp(point.dew_point_c)}</span>
      </div>
    </div>
  );
}

/** Temperature over the course of the activity (hours, user's timezone). */
function TemperatureChart({ weather, startedAt }: { weather: ActivityWeatherView; startedAt: string }) {
  const start = new Date(startedAt).getTime();
  const data = weather.points.map((point) => ({
    time: clockFromSeconds(Math.max(0, Math.round((new Date(point.time).getTime() - start) / 1000))),
    temperature: point.temperature_c,
  }));
  return (
    <div className="mt-4 h-56 w-full">
      <p className="mb-2 text-sm font-medium text-ink-muted">Temperature over the activity</p>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
          <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#6f6d68" }} />
          <YAxis tick={{ fontSize: 11, fill: "#6f6d68" }} domain={["dataMin - 2", "dataMax + 2"]} />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #e3e1dc", fontSize: 12 }}
            formatter={(value) => [`${value}°C`, "Temperature"]}
          />
          <Line
            type="monotone"
            dataKey="temperature"
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

type WeatherCardProps = { activityId: string; startedAt: string; endedAt: string };

export default function WeatherCard({ activityId, startedAt, endedAt }: WeatherCardProps) {
  const { timeZone } = useTimezone();
  const { data: weather, isPending, isError, error, refetch } = useActivityWeather(activityId);
  const fetchMutation = useFetchWeather(activityId);

  // Not fetched yet: a single opt-in action (the app stays offline-capable).
  if (weather === null) {
    return (
      <div>
        <p className="text-sm text-ink-muted">
          Show what the weather was like during this activity — conditions at start and end, plus a
          temperature curve for longer efforts. Fetched on demand from Open-Meteo and cached, so it
          loads instantly next time.
        </p>
        <button
          type="button"
          onClick={() => fetchMutation.mutate()}
          disabled={fetchMutation.isPending}
          className="mt-3 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
        >
          {fetchMutation.isPending ? "Fetching weather…" : "Show weather"}
        </button>
        {fetchMutation.isError && (
          <div className="mt-3">
            <ErrorNote message={fetchMutation.error.message} />
          </div>
        )}
      </div>
    );
  }

  if (isPending) {
    return <Spinner label="Loading weather…" />;
  }

  if (isError || weather === undefined) {
    return (
      <div>
        <ErrorNote message={error instanceof Error ? error.message : "Could not load the weather."} />
        <button type="button" onClick={() => void refetch()} className="mt-2 text-sm font-medium text-accent underline">
          Try again
        </button>
      </div>
    );
  }

  const start = nearestPoint(weather.points, startedAt);
  const end = nearestPoint(weather.points, endedAt);
  // Sub-90-minute efforts read fine as two chips; longer ones earn the curve.
  const longEffort = new Date(endedAt).getTime() - new Date(startedAt).getTime() >= 90 * 60_000;

  return (
    <div>
      {weather.points.length === 1 ? (
        <ConditionChip label="Conditions" point={start} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <ConditionChip label={`Start · ${formatClock(startedAt, timeZone)}`} point={start} />
          <ConditionChip label={`End · ${formatClock(endedAt, timeZone)}`} point={end} />
        </div>
      )}

      {longEffort && <TemperatureChart weather={weather} startedAt={startedAt} />}

      <p className="mt-3 text-xs text-ink-faint">
        Weather data by{" "}
        <a href="https://open-meteo.com/" className="underline" target="_blank" rel="noreferrer">
          Open-Meteo
        </a>{" "}
        (CC BY 4.0), model/grid data for the start point · fetched{" "}
        {formatClock(weather.fetched_at, timeZone)}
      </p>
    </div>
  );
}
