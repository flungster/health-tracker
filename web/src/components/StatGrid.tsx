/** Grid of label/value stat tiles for the activity detail header. */

export type Stat = {
  label: string;
  value: string;
};

export default function StatGrid({ stats }: { stats: Stat[] }) {
  const visible = stats.filter((stat) => stat.value !== "—");
  if (visible.length === 0) {
    return null;
  }
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
      {visible.map((stat) => (
        <div key={stat.label} className="bg-surface px-4 py-3">
          <dt className="text-xs uppercase tracking-wide text-ink-faint">{stat.label}</dt>
          <dd className="mt-1 truncate text-lg font-semibold text-ink">{stat.value}</dd>
        </div>
      ))}
    </dl>
  );
}
