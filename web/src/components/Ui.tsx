/** Small shared UI primitives. */

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-ink-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
      {message}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface px-6 py-16 text-center">
      <p className="text-base font-medium text-ink">{title}</p>
      {hint !== undefined && <p className="mt-1 text-sm text-ink-muted">{hint}</p>}
    </div>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-line bg-surface ${className}`}>
      {children}
    </div>
  );
}
