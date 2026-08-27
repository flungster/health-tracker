/** Connected third-party accounts (provider connections) on the profile page. */

import { useConnectProvider, useDisconnectProvider, useProviderConnection, useProviders } from "../api/hooks";
import type { ProviderInfoView } from "../api/types";
import { formatActivityDate } from "../format";
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

  if (!provider.configured) {
    return (
      <li className="flex items-center justify-between rounded-md border border-line bg-surface px-4 py-3">
        <div>
          <p className="text-sm font-medium text-ink">{provider.description}</p>
          <p className="text-sm text-ink-muted">Not configured on this server.</p>
        </div>
      </li>
    );
  }

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
      <li className="flex items-center justify-between rounded-md border border-line bg-surface px-4 py-3">
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
        <button
          type="button"
          disabled={disconnect.isPending}
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
      </li>
      {disconnect.isError && (
        <li>
          <ErrorNote message={disconnect.error.message} />
        </li>
      )}
    </>
  );
}
