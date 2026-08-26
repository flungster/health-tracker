/** Redirects authenticated visitors away from the public pages. */

import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function PublicOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user !== null) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
