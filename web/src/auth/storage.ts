/** Token and session persistence in localStorage. */

import type { UserView } from "../api/types";

const TOKEN_KEY = "health-tracker.token";
const USER_KEY = "health-tracker.user";

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private mode); the session just will not persist.
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore.
  }
}

export function getAuthToken(): string | null {
  return safeGet(TOKEN_KEY);
}

export function getStoredUser(): UserView | null {
  const raw = safeGet(USER_KEY);
  if (raw === null) {
    return null;
  }
  try {
    return JSON.parse(raw) as UserView;
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: UserView): void {
  safeSet(TOKEN_KEY, token);
  safeSet(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  safeRemove(TOKEN_KEY);
  safeRemove(USER_KEY);
}
