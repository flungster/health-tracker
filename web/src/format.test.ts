/** Unit tests for the display formatters (metric + imperial behaviour). */

import { describe, expect, it } from "vitest";

import { formatDistance, formatElevation, formatPace, formatWeight, paceSuffix } from "./format";

describe("formatDistance", () => {
  it("renders metric meters below a kilometre", () => {
    expect(formatDistance(132, "metric")).toBe("132 m");
  });

  it("renders metric kilometres at two decimals", () => {
    expect(formatDistance(5054.3, "metric")).toBe("5.05 km");
  });

  it("renders imperial miles at one decimal", () => {
    expect(formatDistance(3.1406, "imperial")).toBe("3.1 mi");
  });

  it("renders an em dash for a missing value", () => {
    expect(formatDistance(null)).toBe("—");
  });
});

describe("formatElevation", () => {
  it("renders whole feet in imperial", () => {
    expect(formatElevation(393.7, "imperial")).toBe("394 ft");
  });

  it("keeps the metric behaviour (like a distance)", () => {
    expect(formatElevation(88, "metric")).toBe("88 m");
  });

  it("renders an em dash for a missing value", () => {
    expect(formatElevation(null, "imperial")).toBe("—");
  });
});

describe("formatWeight", () => {
  // The API already converts (M14): an imperial caller's value arrives in lb.
  // The formatter only rounds and labels — it never converts again.
  it("renders whole lb for imperial callers and kg otherwise", () => {
    expect(formatWeight(221.3, "imperial")).toBe("221 lb");
    expect(formatWeight(100.4, "metric")).toBe("100 kg");
  });

  it("renders an em dash for a missing value", () => {
    expect(formatWeight(null)).toBe("—");
  });
});

describe("paceSuffix", () => {
  it("is /km for metric (the default) and /mi otherwise", () => {
    expect(paceSuffix("metric")).toBe("/km");
    expect(paceSuffix()).toBe("/km");
    expect(paceSuffix("imperial")).toBe("/mi");
  });
});

describe("formatPace", () => {
  it('renders the m\'ss" style', () => {
    expect(formatPace(292.8)).toBe('4\'53"');
    expect(formatPace(0)).toBe('0\'00"');
  });

  it("renders an em dash for missing values", () => {
    expect(formatPace(null)).toBe("—");
    expect(formatPace(undefined)).toBe("—");
  });
});
