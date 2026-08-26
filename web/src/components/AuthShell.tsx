/** Public auth card shell shared by Login and Register. */

import type { ReactNode } from "react";

import { Link } from "react-router-dom";

export function AuthShell({ title, subtitle, children }: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-canvas px-4 py-10">
      <span className="text-2xl font-bold tracking-tight text-ink">
        health<span className="text-accent">-tracker</span>
      </span>
      <div className="mt-6 w-full max-w-sm rounded-lg border border-line bg-surface p-6">
        <h1 className="text-lg font-semibold text-ink">{title}</h1>
        {subtitle !== undefined && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}

export function FieldError({ error }: { error: string | null }) {
  if (error === null) {
    return null;
  }
  return <p className="mt-4 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>;
}

export function inputClass(invalid: boolean): string {
  return `w-full rounded-md border px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-accent focus:ring-2 focus:ring-accent/20 ${
    invalid ? "border-danger" : "border-line"
  }`;
}

export function labelClass(): string {
  return "mb-1 block text-sm font-medium text-ink";
}

export function PrimaryButton({ children, type = "submit", disabled = false }: {
  children: ReactNode;
  type?: "button" | "submit";
  disabled?: boolean;
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      className="w-full rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function LinkLine({ children, to, text }: { children: ReactNode; to: string; text: string }) {
  return (
    <p className="mt-4 text-center text-sm text-ink-muted">
      {children}{" "}
      <Link to={to} className="font-medium text-accent hover:text-accent-dark">
        {text}
      </Link>
    </p>
  );
}
