/** Provenance chip: which provider an activity was synced from (M21).

Renders nothing for file imports (`provider` null) — the feed stays clean.
*/

import { capitalize } from "../format";

export default function ProviderBadge({ provider }: { provider: string | null }) {
  if (provider === null) {
    return null;
  }
  return (
    <span className="inline-flex items-center rounded-full border border-line px-2 py-0.5 text-xs font-medium text-ink-muted">
      {capitalize(provider)}
    </span>
  );
}
