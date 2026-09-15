/** Unit tests for the primary's linked-duplicates section (M28b). */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

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
  items: [] as RowStub[],
  isPending: false,
  promoteMutate: vi.fn(),
  unlinkMutate: vi.fn(),
};

vi.mock("../api/hooks", () => ({
  useLinkedDuplicates: (id: string) => {
    if (id === "primary-1") {
      return { data: mocks.items.length > 0 ? { items: mocks.items, units: "metric" } : undefined, isPending: false };
    }
    return { data: { items: mocks.items, units: "metric" }, isPending: mocks.isPending };
  },
  useLinkDuplicate: () => ({ mutate: mocks.promoteMutate, isPending: false, isError: false }),
  useUnlinkDuplicate: () => ({ mutate: mocks.unlinkMutate, isPending: false, isError: false }),
}));

vi.mock("../timezone/context", () => ({
  useTimezone: () => ({ timeZone: null, setTimeZone: vi.fn() }),
}));

import LinkedDuplicatesCard from "./LinkedDuplicatesCard";

function renderSection(): RenderResult {
  return render(
    <MemoryRouter initialEntries={["/activities/primary-1"]}>
      <LinkedDuplicatesCard activityId="primary-1" />
    </MemoryRouter>,
  );
}

function twinRow(provider: string | null = "strava"): RowStub {
  return {
    id: "twin-1",
    sport_type: "running",
    name: "Twin run (provider copy)",
    started_at: "2026-09-11T08:15:30Z",
    duration_seconds: 900,
    moving_seconds: null,
    distance: 5.1,
    calories_kcal: null,
    elevation_gain: null,
    heart_rate_avg_bpm: null,
    provider,
  };
}

describe("LinkedDuplicatesCard", () => {
  it("renders nothing while loading", () => {
    mocks.isPending = true;

    const { container } = render(<LinkedDuplicatesCard activityId="" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when there are no linked duplicates", () => {
    mocks.items = [];

    const { container } = render(<LinkedDuplicatesCard activityId="" />);
    expect(container.firstChild).toBeNull();
  });

  it("shows each linked duplicate with its provenance and actions", () => {
    const fileRow = twinRow(null);
    fileRow.name = "Twin run (file copy)";

    mocks.items = [twinRow(), fileRow];

    renderSection();

    expect(screen.getByText("Linked duplicates")).toBeTruthy();
    // One row per linked duplicate; the provider one gets a badge, the file one none.
    expect(screen.getByRole("link", { name: "Twin run (provider copy)" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Twin run (file copy)" })).toBeTruthy();
    expect(screen.getByText("Strava")).toBeTruthy();
  });

  it("promotes a row after confirmation", () => {
    mocks.items = [twinRow()];

    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderSection();
    fireEvent.click(screen.getByRole("button", { name: "Make this live" }));

    expect(mocks.promoteMutate).toHaveBeenCalledWith({
      duplicate_of: "primary-1",
      make_primary: true,
    });
  });

  it("does not promote without confirmation", () => {
    mocks.items = [twinRow()];

    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderSection();
    fireEvent.click(screen.getByRole("button", { name: "Make this live" }));

    expect(mocks.promoteMutate).not.toHaveBeenCalled();
  });

  it("unlinks a row", () => {
    mocks.items = [twinRow()];

    renderSection();
    fireEvent.click(screen.getByRole("button", { name: "Unlink" }));

    expect(mocks.unlinkMutate).toHaveBeenCalled();
  });
});
