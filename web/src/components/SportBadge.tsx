/** Sport label with a small color dot (calm, neutral tones). */

import { capitalize } from "../format";

const DOT_COLORS: Record<string, string> = {
  running: "bg-accent",
  cycling: "bg-[#4a6fa5]",
  rowing: "bg-[#5a8a9a]",
  strength: "bg-[#8a6f5a]",
  yoga: "bg-[#7a8a5a]",
  hiking: "bg-[#6f7d5a]",
  walking: "bg-[#8a8a7a]",
  swimming: "bg-[#4a8a8a]",
  other: "bg-ink-faint",
};

export default function SportBadge({ sportType }: { sportType: string }) {
  const dot = DOT_COLORS[sportType] ?? DOT_COLORS.other;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-2.5 py-0.5 text-xs font-medium text-ink-muted">
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {capitalize(sportType)}
    </span>
  );
}
