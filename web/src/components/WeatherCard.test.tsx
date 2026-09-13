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

import type { ActivityWeatherView } from "../api/types";
import WeatherCard, { weatherLabel } from "./WeatherCard";

const STARTED = "2026-09-11T08:15:00Z";

/** A two-hour snapshot around the fixture activity (UTC hours). */
function makeWeather(): ActivityWeatherView {
  return {
    id: "weather-1",
    lat: 48.85,
    lon: 2.35,
    fetched_at: "2026-09-11T08:05:00Z",
    points: [
      {
        time: "2026-09-11T08:00:00Z",
        temperature_c: 20.5,
        apparent_temperature_c: 19.7,
        relative_humidity_pct: 54,
        dew_point_c: 10.2,
        weather_code: 3, // Overcast
      },
      {
        time: "2026-09-11T09:00:00Z",
        temperature_c: 24.1,
        apparent_temperature_c: null, // a missing upstream value shows an em dash
        relative_humidity_pct: 48.3,
        dew_point_c: 11.0,
        weather_code: 61, // Light rain
      },
    ],
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
    expect(screen.getByText(/21°/)).toBeTruthy(); // 20.5 rounds to 21
    expect(screen.getByText(/24°/)).toBeTruthy(); // 24.1 rounds to 24
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

