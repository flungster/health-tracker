/** Per-user display time zone: localStorage-seeded, synced with the profile.

 * null = the browser's local timezone (the app default). The stored value only
 * pre-paints before the profile arrives; once it loads, the profile wins —
 * same pattern as UnitsProvider (M14c). No live cross-tab sync: a later load
 * re-syncs from the profile.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useProfile } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";

const STORAGE_KEY = "health-tracker.timezone";

/** The stored choice (localStorage): an IANA name, or null = browser local. */
function readStoredTimeZone(): string | null {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored !== null && stored.trim() !== "" ? stored : null;
}

type TimeZoneContextValue = {
  /** The IANA time zone dates should render in, or null for the browser's. */
  timeZone: string | null;
  /** Adopt a zone (state + localStorage). Used on profile-save success. */
  setTimeZone: (timeZone: string | null) => void;
};

const TimeZoneContext = createContext<TimeZoneContextValue | null>(null);

export function TimezoneProvider({ children }: { children: ReactNode }) {
  const [timeZone, setTimeZoneState] = useState<string | null>(readStoredTimeZone);
  const { user } = useAuth();

  // The profile is the source of truth; null is a real value there (the
  // browser-local default), so sync whenever it has loaded and differs.
  const { data: profile } = useProfile(user !== null);

  useEffect(() => {
    const saved = profile?.timezone;
    if (saved === undefined || saved === timeZone) {
      return;
    }
    setTimeZoneState(saved);
    window.localStorage.setItem(STORAGE_KEY, saved ?? "");
  }, [profile, timeZone]);

  const setTimeZone = useCallback((next: string | null) => {
    window.localStorage.setItem(STORAGE_KEY, next ?? "");
    setTimeZoneState(next);
  }, []);

  return (
    <TimeZoneContext.Provider value={{ timeZone, setTimeZone }}>{children}</TimeZoneContext.Provider>
  );
}

export function useTimezone(): TimeZoneContextValue {
  const ctx = useContext(TimeZoneContext);
  if (ctx === null) {
    throw new Error("useTimezone must be used within a TimezoneProvider");
  }
  return ctx;
}
