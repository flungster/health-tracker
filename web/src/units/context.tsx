/** Per-user display unit system: localStorage-seeded, synced with the profile. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useProfile } from "../api/hooks";
import type { Units } from "../api/types";
import { useAuth } from "../auth/AuthContext";

const STORAGE_KEY = "health-tracker.units";

/** The stored choice (localStorage), or the metric default. */
function readStoredUnits(): Units {
  return window.localStorage.getItem(STORAGE_KEY) === "imperial" ? "imperial" : "metric";
}

type UnitsContextValue = {
  /** The display system unit-bearing values should be rendered in. */
  units: Units;
  /** Adopt a system (state + localStorage). Used on profile-save success. */
  setUnits: (units: Units) => void;
};

const UnitsContext = createContext<UnitsContextValue | null>(null);

export function UnitsProvider({ children }: { children: ReactNode }) {
  const [units, setUnitsState] = useState<Units>(readStoredUnits);
  const { user } = useAuth();

  // The profile is the source of truth: once it loads (and after any
  // ["profile"] invalidation, e.g. a save elsewhere) follow its system. The
  // stored value only pre-paints before the profile arrives; there is no live
  // cross-tab sync — a later load re-syncs from the profile.
  const { data: profile } = useProfile(user !== null);

  useEffect(() => {
    const saved = profile?.units_system;
    if (saved === undefined || saved === units) {
      return;
    }
    setUnitsState(saved);
    window.localStorage.setItem(STORAGE_KEY, saved);
  }, [profile, units]);

  const setUnits = useCallback((next: Units) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    setUnitsState(next);
  }, []);

  return (
    <UnitsContext.Provider value={{ units, setUnits }}>{children}</UnitsContext.Provider>
  );
}

export function useUnits(): UnitsContextValue {
  const ctx = useContext(UnitsContext);
  if (ctx === null) {
    throw new Error("useUnits must be used within a UnitsProvider");
  }
  return ctx;
}
