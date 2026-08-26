/** Gates the app pages behind an authenticated session. */

import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function ProtectedRoute() {
  const { user } = useAuth();
  if (user === null) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
