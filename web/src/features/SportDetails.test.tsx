/** Component tests for the sport detail views (unit-aware display). */

import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

// No vitest globals here, so testing-library's auto-cleanup never registers —
// unmount each test's tree by hand or renders accumulate in the jsdom document.
afterEach(cleanup);

import type { RowingMetricsView, Units, WalkingMetricsView } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { RowingDetail, WalkingDetail } from "./SportDetails";
import { UnitsProvider } from "../units/context";

/** Mount a view with the real provider stack, seeding the stored unit choice. */
function renderWithUnits(stored: Units | null, ui: ReactNode) {
  if (stored !== null) {
    window.localStorage.setItem("health-tracker.units", stored);
  }
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <UnitsProvider>{ui}</UnitsProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("WalkingDetail", () => {
  // A stored choice must not leak between tests.
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("shows pace and distance in the metric system by default", () => {
    const walking: WalkingMetricsView = { avg_pace_seconds: 292.8 };
    renderWithUnits(null, <WalkingDetail walking={walking} distance={5054.3} />);

    expect(screen.getByText("Walking")).toBeTruthy();
    // Values are exactly what the API sent for a metric caller.
    expect(screen.getByText('4\'53" /km')).toBeTruthy();
    expect(screen.getByText("5.05 km")).toBeTruthy();
  });

  it("shows pace and distance in the imperial system when stored", () => {
    // An imperial caller receives already-converted values from the API.
    const walking: WalkingMetricsView = { avg_pace_seconds: 471.2 };
    renderWithUnits("imperial", <WalkingDetail walking={walking} distance={3.1406} />);

    expect(screen.getByText('7\'51" /mi')).toBeTruthy();
    expect(screen.getByText("3.1 mi")).toBeTruthy();
  });

  it("shows an em dash when the walk has no pace", () => {
    const walking: WalkingMetricsView = { avg_pace_seconds: null };
    renderWithUnits(null, <WalkingDetail walking={walking} distance={5054.3} />);

    expect(screen.getByText("—")).toBeTruthy();
  });
});

describe("RowingDetail", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  const rowing: RowingMetricsView = {
    stroke_rate_avg_spm: 26,
    stroke_rate_min_spm: 24,
    stroke_rate_max_spm: 28,
    split_500m_seconds: 145.3,
  };

  it("shows stroke rate and distance in the metric system by default", () => {
    renderWithUnits(null, <RowingDetail rowing={rowing} distance={6000} />);

    expect(screen.getByText("26 spm")).toBeTruthy();
    // The 500 m split stays metre-based in both systems (M14).
    expect(screen.getByText('2\'25"')).toBeTruthy();
    expect(screen.getByText("6.00 km")).toBeTruthy();
  });

  it("shows the converted distance for imperial callers, stroke rate unchanged", () => {
    renderWithUnits("imperial", <RowingDetail rowing={rowing} distance={3.728} />);

    expect(screen.getByText("26 spm")).toBeTruthy();
    expect(screen.getByText('2\'25"')).toBeTruthy();
    expect(screen.getByText("3.7 mi")).toBeTruthy();
  });

  it("shows an em dash when the activity has no distance", () => {
    renderWithUnits(null, <RowingDetail rowing={rowing} distance={null} />);

    expect(screen.getByText("—")).toBeTruthy();
  });
});
