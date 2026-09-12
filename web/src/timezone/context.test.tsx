/** Unit tests for the display-timezone context (M23b): storage seed, setTimeZone. */

import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  authUser = null;
  profileMocks.timezone = undefined;
});

let authUser: unknown = null;
const profileMocks = { timezone: undefined as string | null | undefined };

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: authUser }),
}));

vi.mock("../api/hooks", () => ({
  useProfile: (enabled = true) => {
    if (!enabled || profileMocks.timezone === undefined) {
      return { data: undefined };
    }
    // Simulate the profile having loaded with its stored timezone.
    return { data: { timezone: profileMocks.timezone } };
  },
}));

import { TimezoneProvider, useTimezone } from "./context";

const wrapper = ({ children }: { children: ReactNode }) => (
  <TimezoneProvider>{children}</TimezoneProvider>
);

describe("useTimezone", () => {
  it("starts at null (browser local) when nothing is stored or saved", () => {
    const { result } = renderHook(() => useTimezone(), { wrapper });

    expect(result.current.timeZone).toBeNull();
  });

  it("seeds from a previous session's localStorage value", () => {
    window.localStorage.setItem("health-tracker.timezone", "Europe/Berlin");

    const { result } = renderHook(() => useTimezone(), { wrapper });
    expect(result.current.timeZone).toBe("Europe/Berlin");
  });

  it("setTimeZone updates state and persists to localStorage", () => {
    const { result } = renderHook(() => useTimezone(), { wrapper });

    act(() => result.current.setTimeZone("Asia/Tokyo"));
    expect(result.current.timeZone).toBe("Asia/Tokyo");
    expect(window.localStorage.getItem("health-tracker.timezone")).toBe("Asia/Tokyo");

    act(() => result.current.setTimeZone(null));
    expect(result.current.timeZone).toBeNull();
    // Null is stored as the empty string: "no saved zone" and an untouched key.
    expect(window.localStorage.getItem("health-tracker.timezone")).toBe("");
  });

  it("syncs from the profile once it loads (source of truth)", () => {
    authUser = { id: "user-1" }; // signed in → the profile query is enabled
    window.localStorage.setItem("health-tracker.timezone", "Europe/Berlin"); // stale local value
    profileMocks.timezone = "Asia/Tokyo";

    const { result } = renderHook(() => useTimezone(), { wrapper });
    expect(result.current.timeZone).toBe("Asia/Tokyo"); // profile wins over stale storage
    expect(window.localStorage.getItem("health-tracker.timezone")).toBe("Asia/Tokyo");
  });

  it("a saved browser-local default (null) also wins over stale storage", () => {
    authUser = { id: "user-1" };
    window.localStorage.setItem("health-tracker.timezone", "Europe/Berlin"); // stale local value
    profileMocks.timezone = null;

    const { result } = renderHook(() => useTimezone(), { wrapper });
    expect(result.current.timeZone).toBeNull();
    expect(window.localStorage.getItem("health-tracker.timezone")).toBe("");
  });

  it("throws outside a TimezoneProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useTimezone())).toThrow(/TimezoneProvider/);
    spy.mockRestore();
  });
});
