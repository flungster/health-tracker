/** Unit tests for the photo gallery (M22c): thumbnails, add tile, delete flow. */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

type ImageStub = { id: string; source: string; original_filename: string | null };

const mocks = {
  images: [] as ImageStub[],
  uploadMutate: vi.fn(),
  deleteMutate: vi.fn(),
};

vi.mock("../api/hooks", () => ({
  imageServeUrl: (activityId: string, imageId: string) =>
    `/api/v1/activities/${activityId}/images/${imageId}`,
  useActivityImages: () => ({ data: { items: mocks.images }, isPending: false, isError: false }),
  useUploadImage: () => ({ mutate: mocks.uploadMutate, isPending: false }),
  useDeleteImage: () => ({ mutate: mocks.deleteMutate, isPending: false }),
}));

import ActivityImages from "./ActivityImages";

describe("ActivityImages", () => {
  it("renders a thumbnail per image with the cookie-served URL", () => {
    mocks.images = [
      { id: "img-1", source: "uploaded", original_filename: "holiday.png" },
      { id: "img-2", source: "uploaded", original_filename: null },
    ];

    render(<ActivityImages activityId="act-1" />);

    const first = screen.getByAltText("holiday.png") as HTMLImageElement;
    expect(first.getAttribute("src")).toBe("/api/v1/activities/act-1/images/img-1");
    // A photo without a display name still gets an accessible label.
    expect(screen.getByAltText("Activity photo").getAttribute("src")).toBe(
      "/api/v1/activities/act-1/images/img-2",
    );
  });

  it("shows the empty hint and an add tile when there are no photos", () => {
    mocks.images = [];

    render(<ActivityImages activityId="act-1" />);

    expect(screen.getByText("No photos yet.")).toBeTruthy();
    expect(screen.getByText("Add photos")).toBeTruthy();
  });

  it("deletes a photo after confirmation", () => {
    mocks.images = [{ id: "img-1", source: "uploaded", original_filename: "a.png" }];
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<ActivityImages activityId="act-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Remove photo" }));

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("photo"));
    expect(mocks.deleteMutate).toHaveBeenCalledWith("img-1");

    confirmSpy.mockRestore();
  });

  it("does not delete when the user cancels confirmation", () => {
    mocks.images = [{ id: "img-1", source: "uploaded", original_filename: "a.png" }];
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<ActivityImages activityId="act-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Remove photo" }));

    expect(mocks.deleteMutate).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("shows the empty gallery, not an error note", () => {
    mocks.images = [];

    const { container } = render(<ActivityImages activityId="act-1" />);

    expect(container.querySelector("[role='alert']")).toBeNull();
  });
});
