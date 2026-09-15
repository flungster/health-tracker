/** Unit tests for the linked-duplicate banner (M28b). */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

const mocks = {
  promote: vi.fn(),
  unlink: vi.fn(),
};

vi.mock("../api/hooks", () => ({
  useLinkDuplicate: () => ({ mutate: mocks.promote, isPending: false, isError: false }),
  useUnlinkDuplicate: () => ({ mutate: mocks.unlink, isPending: false, isError: false }),
}));

import DuplicateNotice from "./DuplicateNotice";

function renderBanner() {
  return render(
    <MemoryRouter initialEntries={["/activities/alias-1"]}>
      <DuplicateNotice activityId="alias-1" primaryId="primary-9" />
    </MemoryRouter>,
  );
}

describe("DuplicateNotice", () => {
  it("explains the hidden state and links to the live activity", () => {
    renderBanner();

    expect(
      screen.getByText(/linked as a duplicate of another one, so it does not appear in your feed/i),
    ).toBeTruthy();

    const link = screen.getByRole("link", { name: "Open the live activity" });
    expect(link.getAttribute("href")).toBe("/activities/primary-9");
  });

  it("promotes after confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Make this one live" }));

    expect(mocks.promote).toHaveBeenCalledWith({
      duplicate_of: "primary-9",
      make_primary: true,
    });
  });

  it("does not promote without confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Make this one live" }));

    expect(mocks.promote).not.toHaveBeenCalled();
  });

  it("unlinks without confirmation", () => {
    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Unlink" }));

    expect(mocks.unlink).toHaveBeenCalled();
  });
});
