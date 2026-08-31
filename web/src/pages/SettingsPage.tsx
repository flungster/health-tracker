/** Server settings: the deployment's provider clients (any account may manage). */

import { useEffect, useState, type FormEvent } from "react";

import {
  useDeleteProviderConfig,
  useProviderConfig,
  useProviders,
  useSaveProviderConfig,
} from "../api/hooks";
import type { ProviderInfoView } from "../api/types";
import { inputClass, labelClass } from "../components/AuthShell";
import { Card, ErrorNote, Spinner } from "../components/Ui";

export default function SettingsPage() {
  const { data, isPending, isError, error } = useProviders();

  if (isPending) {
    return <Spinner label="Loading settings…" />;
  }
  if (isError) {
    return <ErrorNote message={error.message} />;
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink">Server settings</h1>
        <p className="mt-1 text-sm text-ink-muted">
          How this server connects to third-party services. Any account on this
          server can change these settings. A client secret is stored encrypted
          and is never shown again after saving.
        </p>
      </div>

      <div>
        <h2 className="text-base font-semibold text-ink">Providers</h2>
        <ul className="mt-3 space-y-4">
          {data.providers.map((provider) => (
            <ProviderConfigCard key={provider.value} provider={provider} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function ProviderConfigCard({ provider }: { provider: ProviderInfoView }) {
  const { data: config, isPending: configPending } = useProviderConfig(provider.value);
  const save = useSaveProviderConfig();
  const remove = useDeleteProviderConfig();

  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [displayName, setDisplayName] = useState("");

  // Prefill the non-secret fields from the stored client (the secret can
  // never be read back, so it always starts blank).
  useEffect(() => {
    if (config === undefined) {
      return;
    }
    setClientId(config.client_id ?? "");
    setDisplayName(config.display_name ?? "");
    setSecret("");
  }, [config]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      provider: provider.value,
      input: { client_id: clientId, client_secret: secret, display_name: displayName },
    });
  }

  function handleRemove() {
    if (
      window.confirm(
        `Remove ${provider.description} from this server? Existing connections are ` +
          "paused — syncing stops until the app is added again.",
      )
    ) {
      remove.mutate(provider.value);
    }
  }

  const configured = config !== undefined ? config.configured : false;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">{provider.description}</h3>
        <span
          className={
            configured
              ? "rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent-dark"
              : "rounded-full bg-line/50 px-2.5 py-0.5 text-xs font-medium text-ink-muted"
          }
        >
          {configured ? "Configured" : "Not configured"}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div>
          <label htmlFor={`client-id-${provider.value}`} className={labelClass()}>
            Client ID
          </label>
          <input
            id={`client-id-${provider.value}`}
            type="text"
            required
            maxLength={128}
            value={clientId}
            onChange={(event) => setClientId(event.target.value)}
            className={inputClass(false)}
            placeholder="12345"
          />
        </div>
        <div>
          <label htmlFor={`client-secret-${provider.value}`} className={labelClass()}>
            Client secret
          </label>
          <input
            id={`client-secret-${provider.value}`}
            type="password"
            autoComplete="new-password"
            maxLength={512}
            value={secret}
            onChange={(event) => setSecret(event.target.value)}
            className={inputClass(false)}
            placeholder={
              configured ? "Leave blank to keep the current secret" : "Required to connect"
            }
          />
        </div>
        <div>
          <label htmlFor={`display-name-${provider.value}`} className={labelClass()}>
            Display name <span className="font-normal text-ink-muted">(optional)</span>
          </label>
          <input
            id={`display-name-${provider.value}`}
            type="text"
            maxLength={100}
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className={inputClass(false)}
            placeholder="Homelab Strava"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={save.isPending || configPending}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
          >
            {save.isPending ? "Saving…" : "Save"}
          </button>
          {configured && (
            <button
              type="button"
              disabled={remove.isPending}
              onClick={handleRemove}
              className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-line/40 disabled:opacity-60"
            >
              {remove.isPending ? "Removing…" : "Remove"}
            </button>
          )}
        </div>
        {save.isSuccess && <p className="text-sm text-accent-dark">Saved.</p>}
        {save.isError && <ErrorNote message={save.error.message} />}
        {remove.isError && <ErrorNote message={remove.error.message} />}
      </form>
    </Card>
  );
}
