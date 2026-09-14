/** Unit tests for the opt-in weather card (M24b): states, chips, chart gating. */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

type FetchState = {
  mutate: ReturnType<typeof vi.fn>;
  isPending: boolean;
  isError: boolean;
};

const mocks = {
  weather: null as unknown, // null = not fetched yet; object = cached snapshot
  isPending: false,
  isError: false,
  error: null as Error | null,
  refetch: vi.fn(),
};

const fetchState: FetchState = { mutate: vi.fn(), isPending: false, isError: false };

vi.mock("../api/hooks", () => ({
  useActivityWeather: () => ({
    data: mocks.weather,
    isPending: mocks.isPending && (mocks.weather as unknown) === undefined,
    isError: mocks.isError,
    error: mocks.error,
    refetch: mocks.refetch,
  }),
  useFetchWeather: () => ({ mutate: fetchState.mutate, isPending: fetchState.isPending }),
}));

vi.mock("../timezone/context", () => ({
  useTimezone: () => ({ timeZone: null, setTimeZone: vi.fn() }),
}));

vi.mock("../theme/context", () => ({
  useTheme: () => ({ theme: "light", dark: false, setTheme: vi.fn() }),
}));

import type { ActivityWeatherView } from "../api/types";
import WeatherCard, { activityWindowPoints, weatherLabel } from "./WeatherCard";

const STARTED = "2026-09-11T08:15:00Z";

/** A two-hour snapshot around the fixture activity (UTC hours). */
function makeWeather(): ActivityWeatherView {
  return {
    id: "weather-1",
    lat: 48.85,
    lon: 2.35,
    fetched_at: "2026-09-11T08:05:00Z",
    units: "metric",
    points: [
      {
        time: "2026-09-11T08:00:00Z",
        temperature: 20.5,
        apparent_temperature: 19.7,
        relative_humidity_pct: 54,
        dew_point: 10.2,
        weather_code: 3, // Overcast
      },
      {
        time: "2026-09-11T09:00:00Z",
        temperature: 24.1,
        apparent_temperature: null, // a missing upstream value shows an em dash
        relative_humidity_pct: 48.3,
        dew_point: 11.0,
        weather_code: 61, // Light rain
      },
    ],
  };
}

/** A full-UTC-day snapshot (24 hourly points), temperature = the hour number. */
function makeDay(day: string): ActivityWeatherView {
  return {
    id: "weather-day",
    lat: 0,
    lon: 0,
    fetched_at: `${day}T23:59:00Z`,
    units: "metric",
    points: Array.from({ length: 24 }, (_, hour) => ({
      time: `${day}T${String(hour).padStart(2, "0")}:00:00Z`,
      temperature: hour + 15, // identifiable per hour (15..38)
      apparent_temperature: null,
      relative_humidity_pct: 50,
      dew_point: null,
      weather_code: 1,
    })),
  };
}

function renderCard(endedAt: string = "2026-09-11T08:50:00Z") {
  return render(
    <WeatherCard activityId="activity-1" startedAt={STARTED} endedAt={endedAt} />,
  );
}

describe("weatherLabel", () => {
  it("maps WMO codes to short labels and falls back for the unknown", () => {
    expect(weatherLabel(0)).toBe("Clear sky");
    expect(weatherLabel(61)).toBe("Light rain");
    expect(weatherLabel(95)).toBe("Thunderstorm");
    expect(weatherLabel(42)).toBe("Code 42"); // unrecognized, but not an error
    expect(weatherLabel(null)).toBe("Unknown");
  });
});

describe("activityWindowPoints", () => {
  it("keeps only the activity's own hours of a full-day snapshot", () => {
    // The report that found this: an 08:28–11:57 local (15:28–18:57 UTC) run
    // stored a whole-day snapshot; plotting all 24 hours stretched the axis to
    // "7h32m" and painted pre-dawn data onto clamped 0:00 ticks.
    const day = makeDay("2026-08-30");

    const windowed = activityWindowPoints(
      day.points,
      "2026-08-30T15:28:21Z",
      "2026-08-30T18:57:01Z",
    );

    // Start hour (15) through end hour (18), both inclusive — 4 hours.
    expect(windowed.map((point) => point.time)).toEqual([
      "2026-08-30T15:00:00Z",
      "2026-08-30T16:00:00Z",
      "2026-08-30T17:00:00Z",
      "2026-08-30T18:00:00Z",
    ]);
  });

  it("always yields at least two points for efforts long enough to earn a curve", () => {
    const day = makeDay("2026-08-30");

    // Tightest case: an exactly 90-minute effort starting mid-hour.
    const windowed = activityWindowPoints(
      day.points,
      "2026-08-30T10:59:00Z",
      "2026-08-30T12:29:00Z",
    );

    expect(windowed.length).toBeGreaterThanOrEqual(2);
  });

  it("spans both days for an activity that crosses UTC midnight", () => {
    const firstDay = makeDay("2026-08-30");
    const secondDay = makeDay("2026-08-31");

    const windowed = activityWindowPoints(
      [...firstDay.points, ...secondDay.points],
      "2026-08-30T23:30:00Z",
      "2026-08-31T00:45:00Z",
    );

    expect(windowed.map((point) => point.time)).toEqual([
      "2026-08-30T23:00:00Z",
      "2026-08-31T00:00:00Z",
    ]);
  });
});

describe("WeatherCard units", () => {
  it("shows imperial temperatures with a °F suffix for an imperial caller", () => {
    const weather = makeWeather();
    // The API converts at read time (M14b): 20.5°C -> 68.9°F, 24.1°C -> 75.38°F
    mocks.weather = {
      ...weather,
      units: "imperial",
      points: weather.points.map((point) => ({ ...point, temperature: point.temperature === null ? null : (point.temperature * 9) / 5 + 32, apparent_temperature: point.apparent_temperature === null ? null : (point.apparent_temperature * 9) / 5 + 32, dew_point: point.dew_point === null ? null : (point.dew_point * 9) / 5 + 32 })),
    };

    renderCard(); // 35-minute effort: chips only, no curve

    expect(screen.getByText(/69°F/)).toBeTruthy(); // 20.5°C -> 68.9 rounds to 69
    expect(screen.getByText(/75°F/)).toBeTruthy(); // 24.1°C -> 75.38 rounds to 75
    expect(screen.queryByText(/°C/)).toBeNull(); // no Celsius anywhere in the card
  });
});

describe("WeatherCard", () => {
  it("asks for the opt-in fetch when no snapshot is cached yet", () => {
    mocks.weather = null;

    renderCard();

    const button = screen.getByRole("button", { name: "Show weather" });
    fireEvent.click(button);
    expect(fetchState.mutate).toHaveBeenCalledTimes(1);
  });

  it("renders start and end conditions from the nearest hours", () => {
    mocks.weather = makeWeather();

    renderCard(); // 35-minute effort: chips only, no curve

    expect(screen.getByText(/Overcast/)).toBeTruthy(); // start hour (08:00)
    expect(screen.getByText(/Light rain/)).toBeTruthy(); // end hour (09:00)
    expect(screen.getByText(/21°C/)).toBeTruthy(); // 20.5 rounds to 21
    expect(screen.getByText(/24°C/)).toBeTruthy(); // 24.1 rounds to 24
    expect(screen.getByText(/Humidity 54%/)).toBeTruthy();
    // A missing upstream value renders as an em dash, not zero or "null".
    expect(screen.getByText(/Feels —/)).toBeTruthy();
    // Attribution (CC BY 4.0) ships with every rendered snapshot.
    expect(screen.getByText(/Open-Meteo/)).toBeTruthy();

    // Sub-90-minute efforts get no temperature curve.
    expect(screen.queryByText("Temperature over the activity")).toBeNull();
  });

  it("adds a temperature curve for longer efforts", () => {
    mocks.weather = makeWeather();

    renderCard("2026-09-11T11:35:00Z"); // 3h20m: the curve earns its place

    expect(screen.getByText("Temperature over the activity")).toBeTruthy();
  });

  it("surfaces an upstream failure with a retry", () => {
    mocks.weather = undefined; // no data at all (not the "null" not-fetched state)
    mocks.isError = true;
    mocks.error = new Error("Weather service error 503.");

    const { container } = renderCard();
    expect(container.textContent).toContain("Weather service error 503.");

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(mocks.refetch).toHaveBeenCalled();
  });

  it("shows a spinner while the first read is in flight", () => {
    mocks.weather = undefined;
    mocks.isPending = true;

    renderCard();
    expect(screen.getByText("Loading weather…")).toBeTruthy();
  });
});

