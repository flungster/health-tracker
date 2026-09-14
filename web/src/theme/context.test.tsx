/** Unit tests for the theme context (M25b): storage seed, setTheme, system + profile sync. */

import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  document.documentElement.classList.remove("dark");
  vi.unstubAllGlobals();
  systemDark = false;
  changeHandlers.length = 0;
  authUser = null;
  profileMocks.theme = undefined;
});

let authUser: unknown = null;
const profileMocks = { theme: undefined as string | undefined };

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: authUser }),
}));

vi.mock("../api/hooks", () => ({
  useProfile: (enabled = true) => {
    if (!enabled || profileMocks.theme === undefined) {
      return { data: undefined };
    }
    // Simulate the profile having loaded with its stored theme.
    return { data: { theme: profileMocks.theme } };
  },
}));

// jsdom has no matchMedia; stub it with a controllable media query. Handlers are
// called the way Leaflet's/browsers' do: with an event whose `matches` is read.
type MediaQueryChangeHandler = (event: { matches: boolean }) => void;

let systemDark = false;
const changeHandlers: MediaQueryChangeHandler[] = [];

function stubMatchMedia() {
  vi.stubGlobal(
    "matchMedia",
    (): {
      matches: boolean;
      addEventListener: (type: "change", handler: MediaQueryChangeHandler) => void;
      removeEventListener: (type: "change", handler: MediaQueryChangeHandler) => void;
    } => ({
      get matches() {
        return systemDark;
      },
      addEventListener: (_type, handler) => {
        changeHandlers.push(handler);
      },
      removeEventListener: (_type, handler) => {
        const index = changeHandlers.indexOf(handler);
        if (index >= 0) {
          changeHandlers.splice(index, 1);
        }
      },
    }),
  );
}

function setSystemDark(next: boolean) {
  systemDark = next;
  for (const handler of [...changeHandlers]) {
    act(() => handler({ matches: next }));
  }
}

import { ThemeProvider, useTheme } from "./context";

const wrapper = ({ children }: { children: ReactNode }) => (
  <ThemeProvider>{children}</ThemeProvider>
);

describe("useTheme", () => {
  it("starts at light when nothing is stored or saved", () => {
    stubMatchMedia();

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("light");
    expect(result.current.dark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("seeds from a previous session's localStorage value", () => {
    stubMatchMedia();
    window.localStorage.setItem("health-tracker.theme", "dark");

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("dark");
    expect(result.current.dark).toBe(true);
    // The pre-paint class is kept in sync once the provider mounts.
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("'system' follows the OS color scheme", () => {
    stubMatchMedia();
    systemDark = true; // the OS is in dark mode
    window.localStorage.setItem("health-tracker.theme", "system");

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("system");
    expect(result.current.dark).toBe(true);
  });

  it("'system' applies a live OS scheme change without a reload", () => {
    stubMatchMedia(); // systemDark starts false (OS light)
    window.localStorage.setItem("health-tracker.theme", "system");

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.dark).toBe(false);

    setSystemDark(true); // the user flips their OS to dark mid-session
    expect(result.current.dark).toBe(true);

    setSystemDark(false); // and back again
    expect(result.current.dark).toBe(false);
  });

  it("setTheme updates state and persists to localStorage", () => {
    stubMatchMedia();

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("light");

    act(() => result.current.setTheme("dark"));
    expect(result.current.theme).toBe("dark");
    expect(result.current.dark).toBe(true);
    expect(window.localStorage.getItem("health-tracker.theme")).toBe("dark");

    act(() => result.current.setTheme("light"));
    expect(result.current.dark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("syncs from the profile once it loads (source of truth)", () => {
    stubMatchMedia();
    authUser = { id: "user-1" }; // signed in → the profile query is enabled
    window.localStorage.setItem("health-tracker.theme", "light"); // stale local value
    profileMocks.theme = "dark";

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("dark"); // profile wins over stale storage
    expect(window.localStorage.getItem("health-tracker.theme")).toBe("dark");
  });

  it("throws outside a ThemeProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useTheme())).toThrow(/ThemeProvider/);
    spy.mockRestore();
  });
});
