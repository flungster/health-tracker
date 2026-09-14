/** Unit tests for the header: the user's name is the profile entry point. */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { first_name: "Maya", last_name: "Doe", email: "maya@example.com" },
    logout: vi.fn(),
  }),
}));

import Layout from "./Layout";

function renderHeader() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Layout />
    </MemoryRouter>,
  );
}

describe("Layout header", () => {
  it("links the user's name to /profile (the profile entry point)", () => {
    renderHeader();

    const name = screen.getByRole("link", { name: "Maya" });
    expect(name).toBeTruthy();
    expect(name.getAttribute("href")).toBe("/profile");
  });

  it("has no separate Profile nav item (the name replaced it)", () => {
    renderHeader();

    expect(screen.queryByRole("link", { name: "Profile" })).toBeNull();
  });

  it("keeps the other nav items", () => {
    renderHeader();

    expect(screen.getByRole("link", { name: "Activities" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Upload" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Server settings" })).toBeTruthy();
  });
});
