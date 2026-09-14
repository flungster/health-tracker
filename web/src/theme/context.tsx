/** Per-user UI theme: localStorage-seeded pre-paint, synced with the profile. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useProfile } from "../api/hooks";
import type { Theme } from "../api/types";
import { useAuth } from "../auth/AuthContext";

const STORAGE_KEY = "health-tracker.theme";
const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

function isStoredTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark" || value === "system";
}

/** The stored choice (localStorage), or the light default. */
function readStoredTheme(): Theme {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return isStoredTheme(stored) ? stored : "light";
}

/** Whether a choice resolves to the dark theme right now. */
function resolveDark(theme: Theme): boolean {
  if (theme === "dark") return true;
  if (theme === "light") return false;
  // system: follow the OS color scheme.
  if (typeof window.matchMedia !== "function") return false; // jsdom without a stub
  return window.matchMedia(DARK_MEDIA_QUERY).matches;
}

type ThemeContextValue = {
  /** The stored choice ("light" / "dark" / "system"). */
  theme: Theme;
  /** Whether the dark palette is in effect (the resolution of `theme`). */
  dark: boolean;
  /** Adopt a choice (state + localStorage). Used on profile-save success. */
  setTheme: (theme: Theme) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme);
  const { user } = useAuth();

  // The profile is the source of truth: once it loads (and after any
  // ["profile"] invalidation, e.g. a save elsewhere) follow its theme. The
  // stored value only pre-paints before the profile arrives; there is no live
  // cross-tab sync — a later load re-syncs from the profile. The server never
  // sends null (a stored NULL renders as "light"), so a plain ?? would do; the
  // guard keeps an unexpected value from clobbering a valid stored choice.
  const { data: profile } = useProfile(user !== null);

  useEffect(() => {
    const saved = profile?.theme;
    if (saved === undefined || !isStoredTheme(saved) || saved === theme) {
      return;
    }
    setThemeState(saved);
    window.localStorage.setItem(STORAGE_KEY, saved);
  }, [profile, theme]);

  // "system" follows the OS live: re-resolve whenever the media query changes
  // (an OS theme switch mid-session applies without a reload).
  const [systemDark, setSystemDark] = useState<boolean>(() => resolveDark("system"));

  useEffect(() => {
    if (theme !== "system" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(DARK_MEDIA_QUERY);
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [theme]);

  const dark = theme === "system" ? systemDark : resolveDark(theme);

  // Keep the pre-paint class (set by index.html) in sync with the resolved
  // theme, including after a profile load or an OS scheme change.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const setTheme = useCallback((next: Theme) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, dark, setTheme }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === null) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
