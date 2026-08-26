/** Authentication state: session user plus login/register/logout actions. */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { apiRequest } from "../api/client";
import type { AuthResponseView, UserView } from "../api/types";
import { clearAuth, getStoredUser, setAuth } from "./storage";

export type RegisterInput = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
};

type AuthContextValue = {
  user: UserView | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserView | null>(() => getStoredUser());

  const login = useCallback(async (email: string, password: string) => {
    const body = await apiRequest<AuthResponseView>("/api/v1/auth/login", {
      method: "POST",
      json: { email, password },
    });
    setAuth(body.token, body.user);
    setUser(body.user);
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    const body = await apiRequest<AuthResponseView>("/api/v1/auth/register", {
      method: "POST",
      json: input,
    });
    setAuth(body.token, body.user);
    setUser(body.user);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, login, register, logout }),
    [user, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
