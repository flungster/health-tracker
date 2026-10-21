/** Unit tests for the library-wide duplicate scan card (M29b). */

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

type RowStub = {
  id: string;
  sport_type: string;
  name: string;
  started_at: string;
  duration_seconds: number;
  moving_seconds: number | null;
  distance: number | null;
  calories_kcal: number | null;
  elevation_gain: number | null;
  heart_rate_avg_bpm: number | null;
  provider: string | null;
};

const mocks = {
  scanMutate: vi.fn(),
  linkMutate: vi.fn(),
  // Which primary each rendered group's linking hook was created for.
  linkPrimaries: [] as string[],
  scanIsPending: false,
  scanIsError: false,
  linkIsPending: false,
  linkIsError: false,
};

const scanError = new Error("The server did not respond.");
const linkError = new Error("That activity could not be linked.");

vi.mock("../api/hooks", () => ({
  useDuplicateScan: () => ({
    mutate: mocks.scanMutate,
    isPending: mocks.scanIsPending,
    isError: mocks.scanIsError,
    error: scanError,
  }),
  useLinkDuplicateGroup: (primaryId: string) => {
    mocks.linkPrimaries.push(primaryId);
    return { mutate: mocks.linkMutate, isPending: mocks.linkIsPending, isError: mocks.linkIsError, error: linkError };
  },
}));

vi.mock("../timezone/context", () => ({
  useTimezone: () => ({ timeZone: "UTC", setTimeZone: vi.fn() }),
}));

import DuplicateScanCard from "./DuplicateScanCard";

function renderCard(): RenderResult {
  return render(
    <MemoryRouter initialEntries={["/activities"]}>
      <DuplicateScanCard />
    </MemoryRouter>,
  );
}

function row(overrides: Partial<RowStub> & { id: string; name: string }): RowStub {
  return {
    sport_type: "running",
    started_at: "2026-09-11T08:15:30Z",
    duration_seconds: 1200,
    moving_seconds: null,
    distance: 5_123,
    calories_kcal: null,
    elevation_gain: null,
    heart_rate_avg_bpm: null,
    provider: null,
    ...overrides,
  };
}

const runA = () => row({ id: "run-a", name: "Morning run (GPX)" });
const runB = () => row({ id: "run-b", name: "Morning run (Strava)", provider: "strava" });
const runC = () => row({ id: "run-c", name: "Morning run (fitness tracker)", provider: null });

function clickScan() {
  fireEvent.click(screen.getByRole("button", { name: /scan (library for duplicates|again)/i }));
}

/** Trigger a scan and replay its onSuccess with the given report. Each group is
 *  passed as its member rows (wrapped in `{ activities }` per the view shape). */
async function scanSuccess(groups: RowStub[][], units: "metric" | "imperial" = "metric") {
  clickScan();
  const call = mocks.scanMutate.mock.calls.at(-1);
  if (call === undefined) {
    throw new Error("the scan was not triggered");
  }
  await act(async () => {
    (call[1] as { onSuccess: (data: unknown) => void }).onSuccess({
      groups: groups.map((activities) => ({ activities })),
      units,
    });
  });
}

function linkButtonName(count: number) {
  return count === 1 ? "Link 1 as duplicate" : `Link ${count} as duplicates`;
}

describe("DuplicateScanCard", () => {
  beforeEach(() => {
    mocks.scanMutate.mockClear();
    mocks.linkMutate.mockClear();
    mocks.linkPrimaries.length = 0;
    mocks.scanIsPending = false;
    mocks.scanIsError = false;
    mocks.linkIsPending = false;
    mocks.linkIsError = false;
  });

  it("offers the scan as an opt-in action before anything runs", () => {
    renderCard();

    const button = screen.getByRole("button", { name: "Scan library for duplicates" });
    expect(screen.getByText(/whole library/)).toBeTruthy();

    fireEvent.click(button);
    expect(mocks.scanMutate).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state while the scanner runs", () => {
    mocks.scanIsPending = true;

    renderCard();

    expect(screen.getByRole("status").textContent ?? "").toContain("Scanning your library…");
    expect(screen.queryByRole("button", { name: "Scan library for duplicates" })).toBeNull();
  });

  it("surfaces a failed first scan with a retry", () => {
    mocks.scanIsError = true;

    renderCard();

    expect(screen.getByText("The server did not respond.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(mocks.scanMutate).toHaveBeenCalledTimes(1);
  });

  it("reports a clean library as the empty state", async () => {
    renderCard();

    await scanSuccess([]);

    expect(screen.getByText(/No duplicate activities found/)).toBeTruthy();
    expect(screen.queryByRole("radio")).toBeNull();
    // The report stays available with a way to run the sweep again.
    expect(screen.getByRole("button", { name: "Scan again" })).toBeTruthy();
  });

  it("renders each group member with its name, provenance and metrics", async () => {
    renderCard();

    await scanSuccess([[runA(), runB()]]);

    expect(screen.getByRole("heading", { name: "Duplicate scan" })).toBeTruthy();
    expect(screen.getByText(/These 2 activities look like the same workout/)).toBeTruthy();

    // One row per member, linked to its own detail page; the provider copy gets a badge.
    expect(screen.getByRole("link", { name: "Morning run (GPX)" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Morning run (Strava)" })).toBeTruthy();
    expect(screen.getAllByText("Strava")).toHaveLength(1);

    // Dates render in the display timezone; metrics follow the view's units (metric).
    expect(screen.getAllByText(/08:15/)).toHaveLength(2); // UTC clock
    expect(screen.getAllByText(/5\.12 km/)).toHaveLength(2); // 5_123 m
    expect(screen.getAllByText(/20m 0s/)).toHaveLength(2); // 1_200 s

    // Both members are selectable; the earliest (first) is preselected to keep.
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(2);
    expect((radios[0] as HTMLInputElement).checked).toBe(true);
  });

  it("renders imperial metrics when the scan's units say so", async () => {
    const rideA = row({ id: "ride-a", name: "Ride A (GPX)", sport_type: "cycling", distance: 3.2, duration_seconds: 1500 });
    const rideB = row({ id: "ride-b", name: "Ride B (Strava)", sport_type: "cycling", provider: "strava", distance: 3.2, duration_seconds: 1500 });

    renderCard();

    await scanSuccess([[rideA, rideB]], "imperial");

    expect(screen.getAllByText(/3\.2 mi/)).toHaveLength(2);
    expect(screen.getAllByText(/25m 0s/)).toHaveLength(2);
  });

  it("links the other member to the preselected (earliest) activity", async () => {
    renderCard();

    await scanSuccess([[runA(), runB()]]);

    fireEvent.click(screen.getByRole("button", { name: linkButtonName(1) }));

    expect(mocks.linkPrimaries.at(-1)).toBe("run-a");
    const call = mocks.linkMutate.mock.calls[0];
    expect(call?.[0]).toEqual(["run-b"]); // only the non-kept member, in group order
    expect(typeof (call?.[1] as { onSuccess?: unknown })?.onSuccess).toBe("function");
  });

  it("links to a different member when another radio is chosen", async () => {
    renderCard();

    await scanSuccess([[runA(), runB()]]);

    fireEvent.click(screen.getByRole("radio", { name: /Morning run \(Strava\)/ }));
    fireEvent.click(screen.getByRole("button", { name: linkButtonName(1) }));

    expect(mocks.linkPrimaries.at(-1)).toBe("run-b");
    const call = mocks.linkMutate.mock.calls[0];
    expect(call?.[0]).toEqual(["run-a"]);
  });

  it("links every non-kept member of a larger group in order", async () => {
    renderCard();

    await scanSuccess([[runA(), runB(), runC()]]);

    fireEvent.click(screen.getByRole("button", { name: linkButtonName(2) }));

    const call = mocks.linkMutate.mock.calls[0];
    expect(call?.[0]).toEqual(["run-b", "run-c"]);
  });

  it("shows a resolved summary once the links succeed", async () => {
    renderCard();

    await scanSuccess([[runA(), runB()]]);

    fireEvent.click(screen.getByRole("button", { name: linkButtonName(1) }));
    const call = mocks.linkMutate.mock.calls[0];
    await act(async () => {
      (call?.[1] as { onSuccess: () => void }).onSuccess();
    });

    expect(screen.getByText(/Linked 1 as duplicate of/)).toBeTruthy();
    // The kept activity is named (and linked) in the summary; no action left to take.
    expect(screen.getAllByRole("link", { name: "Morning run (GPX)" })).toHaveLength(2); // row + summary
    expect(screen.queryByRole("button", { name: linkButtonName(1) })).toBeNull();
    expect((screen.getAllByRole("radio")[0] as HTMLInputElement).disabled).toBe(true);
  });

  it("keeps the group actionable when linking fails", async () => {
    mocks.linkIsError = true;

    renderCard();

    await scanSuccess([[runA(), runB()]]);
    fireEvent.click(screen.getByRole("button", { name: linkButtonName(1) }));

    // The error is reported per group; the (idempotent) action stays available to retry.
    expect(screen.getByText("That activity could not be linked.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: linkButtonName(1) })).toBeTruthy();
  });

  it("runs the sweep again from a previous result", async () => {
    renderCard();

    await scanSuccess([[runA(), runB()]]);

    fireEvent.click(screen.getByRole("button", { name: "Scan again" }));
    expect(mocks.scanMutate).toHaveBeenCalledTimes(2);
  });
});
