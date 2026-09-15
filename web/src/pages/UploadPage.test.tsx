/** Unit tests for the post-import duplicate confirmation (M28b). */

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

type RowStub = {
  id: string;
  name: string;
  provider: string | null;
  started_at: string;
};

const mocks = {
  importMutate: vi.fn(),
  linkMutate: vi.fn(),
  candidates: [] as RowStub[],
};

vi.mock("../api/hooks", () => ({
  useImportActivity: () => ({ mutate: mocks.importMutate, isPending: false, isError: false }),
  useLinkDuplicate: () => ({ mutate: mocks.linkMutate, isPending: false, isError: false }),
  useDuplicateCandidates: () => ({ data: { items: mocks.candidates, units: "metric" } }),
  useSports: () => ({ data: { sports: [] as Array<{ value: string; description: string }> } }),
}));

vi.mock("../timezone/context", () => ({
  useTimezone: () => ({ timeZone: null, setTimeZone: vi.fn() }),
}));

import UploadPage from "./UploadPage";

function Probe() {
  const location = useLocation();
  return <div data-testid="probe">{location.pathname}</div>;
}

function renderPage(): RenderResult {
  return render(
    <MemoryRouter initialEntries={["/upload"]}>
      <Routes>
        <Route path="/upload" element={<UploadPage />} />
        <Route path="*" element={<Probe />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function selectFile() {
  // react-dropzone validates the file type asynchronously.
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["gpx-bytes"], "run.gpx", { type: "application/octet-stream" })] } });
  await screen.findByRole("button", { name: "Import activity" });
}

async function triggerImportSuccess() {
  // The component called mutate(input, options) — replay its onSuccess. It is a
  // state update outside React event handling, so flush it inside act().
  const call = mocks.importMutate.mock.calls.at(-1);
  if (call === undefined) {
    throw new Error("import was not triggered");
  }
  await act(async () => {
    call[1].onSuccess({ id: "new-activity" });
  });
}

const CANDIDATES: RowStub[] = [
  { id: "existing-1", name: "Morning run (Strava)", provider: "strava", started_at: "2026-09-11T08:15Z" },
  { id: "existing-2", name: "Morning run (GPX)", provider: null, started_at: "2026-09-11T08:15Z" },
];

describe("UploadPage duplicate confirmation", () => {
  it("goes straight to the detail page when there are no candidates", async () => {
    mocks.candidates = [];

    renderPage();
    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Import activity" }));

    expect(mocks.importMutate).toHaveBeenCalledTimes(1);
    await triggerImportSuccess();

    // No candidates: the effect navigates to the new activity's detail page.
    expect((await screen.findByTestId("probe")).textContent).toBe("/activities/new-activity");
  });

  it("asks for confirmation when candidates exist", async () => {
    mocks.candidates = CANDIDATES;

    renderPage();
    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Import activity" }));

    expect(mocks.importMutate).toHaveBeenCalledTimes(1);
    await triggerImportSuccess();

    // The review card lists both candidates; nothing navigated yet.
    expect(screen.getByRole("radio", { name: /Morning run \(Strava\)/ })).toBeTruthy();
    expect(screen.getByRole("radio", { name: /Morning run \(GPX\)/ })).toBeTruthy();
    expect(screen.queryByTestId("probe")).toBeNull();

    // The strongest match (first) is preselected.
    expect((screen.getByRole("radio", { name: /Morning run \(Strava\)/ }) as HTMLInputElement).checked).toBe(true);
  });

  it("links the import to the chosen primary and lands on its detail page", async () => {
    mocks.candidates = CANDIDATES;

    renderPage();
    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Import activity" }));

    await triggerImportSuccess();
    // Choose the second candidate.
    fireEvent.click(screen.getByRole("radio", { name: /Morning run \(GPX\)/ }));
    fireEvent.click(screen.getByRole("button", { name: "Link as duplicate" }));

    expect(mocks.linkMutate).toHaveBeenCalledTimes(1);
    const call = mocks.linkMutate.mock.calls[0];
    expect(call[0]).toEqual({ duplicate_of: "existing-2" });

    // Replay the mutation's onSuccess to follow through on navigation.
    call[1].onSuccess();
    expect((await screen.findByTestId("probe")).textContent).toBe("/activities/existing-2");
  });

  it("keeps the import separate when asked", async () => {
    mocks.candidates = CANDIDATES;

    renderPage();
    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Import activity" }));

    await triggerImportSuccess();
    fireEvent.click(screen.getByRole("button", { name: "Keep as separate activity" }));

    expect(mocks.linkMutate).not.toHaveBeenCalled();
    expect((await screen.findByTestId("probe")).textContent).toBe("/activities/new-activity");
  });

  it("defaults to the strongest match when no radio is picked", async () => {
    mocks.candidates = CANDIDATES;

    renderPage();
    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Import activity" }));

    await triggerImportSuccess();
    fireEvent.click(screen.getByRole("button", { name: "Link as duplicate" }));

    const call = mocks.linkMutate.mock.calls[0];
    expect(call?.[0]).toEqual({ duplicate_of: "existing-1" });
  });
});
