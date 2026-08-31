/** Connected third-party accounts (provider connections) on the profile page. */

import { useState } from "react";
import { Link } from "react-router-dom";

import {
  useConnectProvider,
  useDisconnectProvider,
  useProviderConnection,
  useProviders,
  useSyncProvider,
  useUpdateProviderConnection,
} from "../api/hooks";
import type { ProviderConnectionView, ProviderInfoView } from "../api/types";
import { dateDaysAgo, formatActivityDate } from "../format";
import { Card, ErrorNote, Spinner } from "./Ui";

export default function ConnectedAccounts() {
  const { data, isPending, isError, error } = useProviders();

  if (isPending) {
    return <Spinner label="Loading connected accounts…" />;
  }
  if (isError) {
    return <ErrorNote message={error.message} />;
  }

  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-ink">Connected accounts</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Pull your activities from a connected service. Only your own account is
        read, and everything lands in your local data.
      </p>
      <ul className="mt-4 space-y-3">
        {data.providers.map((provider) => (
          <ProviderRow key={provider.value} provider={provider} />
        ))}
      </ul>
    </Card>
  );
}

function ProviderRow({ provider }: { provider: ProviderInfoView }) {
  const { data: connection, isPending, isError, error } = useProviderConnection(
    provider.value,
  );
  const connect = useConnectProvider();
  const disconnect = useDisconnectProvider();
  const sync = useSyncProvider();
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [rescanOpen, setRescanOpen] = useState(false);
  const [rescanDate, setRescanDate] = useState("");

  if (isPending) {
    return <Spinner label={`Checking ${provider.description}…`} />;
  }

  if (isError || connection === undefined) {
    return (
      <li>
        <ErrorNote message={error instanceof Error ? error.message : "Failed to load."} />
      </li>
    );
  }

  if (!provider.configured) {
    // The deployment's client was never saved (or was removed): the
    // connection, if any, is orphaned until it is saved again.
    if (connection === null) {
      return (
        <li className="flex items-center justify-between rounded-md border border-line bg-surface px-4 py-3">
          <div>
            <p className="text-sm font-medium text-ink">{provider.description}</p>
            <p className="text-sm text-ink-muted">
              Not configured on this server.{" "}
              <Link to="/settings" className="font-medium text-accent-dark underline">
                Set it up in Server settings
              </Link>
            </p>
          </div>
        </li>
      );
    }
    return (
      <li className="rounded-md border border-line bg-surface px-4 py-3">
        <p className="text-sm font-medium text-ink">
          {provider.description}
          {connection.display_name !== null ? ` · ${connection.display_name}` : ""}
        </p>
        <p className="mt-1 text-sm text-ink-muted">
          Sync paused — {provider.description} is not configured on this server.
          Its activities stay in your data.
        </p>
        <Link
          to="/settings"
          className="mt-2 inline-block text-sm font-medium text-accent-dark underline"
        >
          Re-add the app in Server settings to resume syncing
        </Link>
      </li>
    );
  }

  if (connection === null) {
    return (
      <li className="flex items-center justify-between rounded-md border border-line bg-surface px-4 py-3">
        <div>
          <p className="text-sm font-medium text-ink">{provider.description}</p>
          <p className="text-sm text-ink-muted">Not connected.</p>
        </div>
        <button
          type="button"
          disabled={connect.isPending}
          onClick={() => connect.mutate(provider.value)}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
        >
          {connect.isPending ? "Opening…" : "Connect"}
        </button>
      </li>
    );
  }

  return (
    <>
      <li className="rounded-md border border-line bg-surface px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-ink">
              {provider.description}
              {connection.display_name !== null ? ` · ${connection.display_name}` : ""}
            </p>
            <p className="text-sm text-ink-muted">
              Connected {formatActivityDate(connection.connected_at)}
              {connection.last_sync_at !== null
                ? ` · Last synced ${formatActivityDate(connection.last_sync_at)}`
                : " · Not synced yet"}
            </p>
          </div>
          <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={sync.isPending || disconnect.isPending}
            onClick={() => {
              setSyncMessage(null);
              sync.mutate(
                { provider: provider.value },
                {
                  onSuccess: (data) =>
                    setSyncMessage(
                      data.imported > 0
                        ? `Imported ${data.imported} new activit${data.imported === 1 ? "y" : "ies"}.`
                        : "All up to date.",
                    ),
                },
              );
            }}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
          >
            {sync.isPending ? "Syncing…" : "Sync"}
          </button>
          <button
            type="button"
            disabled={sync.isPending}
            onClick={() => setRescanOpen(!rescanOpen)}
            className="rounded-md border border-line px-3 py-1.5 text-sm font-semibold text-ink-muted transition-colors hover:bg-line/40 hover:text-ink disabled:opacity-60"
          >
            Rescan from…
          </button>
          <button
            type="button"
            disabled={sync.isPending || disconnect.isPending}
            onClick={() => {
              if (
                window.confirm(
                  `Disconnect ${provider.description}? Their activities stay in your data.`,
                )
              ) {
                disconnect.mutate(provider.value);
              }
            }}
            className="rounded-md border border-line px-3 py-1.5 text-sm font-semibold text-ink transition-colors hover:bg-line/40 disabled:opacity-60"
          >
            {disconnect.isPending ? "Disconnecting…" : "Disconnect"}
          </button>
          </div>
        </div>
        {rescanOpen && (
          <div className="mt-3 border-t border-line pt-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-ink-muted">Re-walk the history from</span>
              <input
                type="date"
                aria-label={`Rescan from date for ${provider.value}`}
                value={rescanDate}
                disabled={sync.isPending}
                onChange={(event) => setRescanDate(event.target.value)}
                className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink outline-none focus:border-accent disabled:opacity-60"
              />
              <button
                type="button"
                disabled={sync.isPending || rescanDate === ""}
                onClick={() => {
                  setSyncMessage(null);
                  sync.mutate(
                    { provider: provider.value, since: rescanDate },
                    {
                      onSuccess: (data) => {
                        setSyncMessage(
                          data.imported > 0
                            ? `Rescan imported ${data.imported} new activit${data.imported === 1 ? "y" : "ies"}.`
                            : "Nothing new since that date.",
                        );
                        setRescanOpen(false);
                      },
                    },
                  );
                }}
                className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
              >
                {sync.isPending ? "Working…" : "Start rescan"}
              </button>
            </div>
            <p className="mt-2 text-xs text-ink-faint">
              One-off: this run imports activities started on or after the date, whatever the
              import-from floor is set to. Activities you already imported are skipped.
            </p>
          </div>
        )}
        <SyncFloorControl provider={provider.value} connection={connection} />
      </li>
      {(syncMessage !== null || sync.isError || disconnect.isError) && (
        <li className="space-y-2">
          {syncMessage !== null && <p className="text-sm text-accent-dark">{syncMessage}</p>}
          {sync.isError && <ErrorNote message={sync.error.message} />}
          {disconnect.isError && <ErrorNote message={disconnect.error.message} />}
        </li>
      )}
    </>
  );
}

const FLOOR_PRESETS: Array<{ label: string; days: number | null }> = [
  { label: "All time", days: null },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "1 year", days: 365 },
];

/** The connection's import-from floor: presets plus a custom date. */
function SyncFloorControl({
  provider,
  connection,
}: {
  provider: string;
  connection: ProviderConnectionView;
}) {
  const update = useUpdateProviderConnection();
  const [error, setError] = useState<string | null>(null);

  // The stored floor is UTC midnight, so its date part is the chosen date.
  const current = connection.sync_since !== null ? connection.sync_since.slice(0, 10) : null;

  function setFloor(syncSince: string | null) {
    setError(null);
    update.mutate(
      { provider, syncSince },
      {
        onError: (mutationError) =>
          setError(
            mutationError instanceof Error ? mutationError.message : "Failed to save.",
          ),
      },
    );
  }

  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-muted">Import from</span>
        {FLOOR_PRESETS.map((preset) => {
          const value = preset.days === null ? null : dateDaysAgo(preset.days);
          const active = current === value;
          return (
            <button
              key={preset.label}
              type="button"
              disabled={update.isPending}
              onClick={() => setFloor(value)}
              className={
                active
                  ? "rounded-full bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-dark"
                  : "rounded-full border border-line px-2.5 py-1 text-xs font-medium text-ink-muted transition-colors hover:bg-line/40 hover:text-ink disabled:opacity-60"
              }
            >
              {preset.label}
            </button>
          );
        })}
        <input
          type="date"
          aria-label={`Import from date for ${provider}`}
          value={current ?? ""}
          disabled={update.isPending}
          onChange={(event) => {
            if (event.target.value !== "") {
              setFloor(event.target.value);
            }
          }}
          className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink outline-none focus:border-accent disabled:opacity-60"
        />
      </div>
      {error !== null && <p className="mt-2 text-sm text-danger">{error}</p>}
    </div>
  );
}
