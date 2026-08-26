/** Authenticated shell: header with navigation, then the routed page. */

import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const linkBase =
  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors";
const linkIdle = "text-ink-muted hover:bg-canvas hover:text-ink";
const linkActive = "bg-accent-soft text-accent-dark";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-6 px-4 py-3">
          <span className="text-lg font-bold tracking-tight text-ink">
            health<span className="text-accent">-tracker</span>
          </span>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkIdle}`}>
              Activities
            </NavLink>
            <NavLink to="/upload" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkIdle}`}>
              Upload
            </NavLink>
            <NavLink to="/profile" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkIdle}`}>
              Profile
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {user !== null && (
              <span className="hidden text-sm text-ink-muted sm:inline">
                {user.first_name}
              </span>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-muted transition-colors hover:border-ink-faint hover:text-ink"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-line py-4 text-center text-xs text-ink-faint">
        self-hosted activity tracking
      </footer>
    </div>
  );
}
