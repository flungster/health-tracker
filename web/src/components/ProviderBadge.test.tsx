/** Unit tests for the provenance chip (M21): provider value or nothing. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ProviderBadge from "./ProviderBadge";

describe("ProviderBadge", () => {
  it("renders the capitalized provider value", () => {
    render(<ProviderBadge provider="strava" />);

    expect(screen.getByText("Strava")).toBeTruthy();
  });

  it("renders nothing for file imports (provider null)", () => {
    const { container } = render(<ProviderBadge provider={null} />);

    expect(container.innerHTML).toBe("");
  });
});
