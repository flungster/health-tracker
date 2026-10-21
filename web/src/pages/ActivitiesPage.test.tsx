/** The activity feed hosts the library-wide duplicate scan entry point (M29b). */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

const mocks = {
  scanMutate: vi.fn(),
};

vi.mock("../api/hooks", () => ({
  useActivitiesInfinite: () => ({
    data: { pages: [] },
    isPending: false,
    isError: false,
    fetchNextPage: vi.fn(),
    isFetchingNextPage: false,
    hasNextPage: false,
  }),
  useDuplicateScan: () => ({ mutate: mocks.scanMutate, isPending: false, isError: false }),
  useLinkDuplicateGroup: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

vi.mock("../timezone/context", () => ({
  useTimezone: () => ({ timeZone: null, setTimeZone: vi.fn() }),
}));

import ActivitiesPage from "./ActivitiesPage";

function renderPage(): RenderResult {
  return render(
    <MemoryRouter initialEntries={["/activities"]}>
      <Routes>
        <Route path="/activities" element={<ActivitiesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ActivitiesPage duplicate scan", () => {
  beforeEach(() => {
    mocks.scanMutate.mockClear();
  });

  it("shows the scan card next to an empty feed", () => {
    renderPage();

    expect(screen.getByRole("button", { name: "Scan library for duplicates" })).toBeTruthy();
    expect(screen.getByText("No activities yet")).toBeTruthy();
  });

  it("triggering the scan calls the API hook", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Scan library for duplicates" }));
    expect(mocks.scanMutate).toHaveBeenCalledTimes(1);
  });
});
