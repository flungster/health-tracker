/** Import a GPX/TCX/FIT file, with optional sport and name overrides.

After the import succeeds, the app checks whether this looks like a workout
you already have (M28): when it does, you confirm — link the new row as a
duplicate of an existing one (which stays live) or keep it separate. */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  useDuplicateCandidates,
  useImportActivity,
  useLinkDuplicate,
  useSports,
} from "../api/hooks";
import ProviderBadge from "../components/ProviderBadge";
import UploadZone from "../components/UploadZone";
import { Card, ErrorNote } from "../components/Ui";
import { formatActivityDate, formatClock } from "../format";
import { useTimezone } from "../timezone/context";

export default function UploadPage() {
  const navigate = useNavigate();
  const { timeZone } = useTimezone();
  const { data: sportsData } = useSports();
  const importMutation = useImportActivity();

  const [file, setFile] = useState<File | null>(null);
  const [sportType, setSportType] = useState<string>("");
  const [name, setName] = useState<string>("");

  // The just-imported activity while its duplicate candidates are checked.
  const [importedId, setImportedId] = useState<string | null>(null);
  const [selectedPrimary, setSelectedPrimary] = useState<string>("");

  const { data: candidatesData } = useDuplicateCandidates(importedId ?? "");
  const linkMutation = useLinkDuplicate(importedId ?? "");

  const sports = sportsData?.sports ?? [];
  const candidates = importedId !== null ? (candidatesData?.items ?? []) : [];

  // No plausible match: straight through to the new activity's detail page.
  useEffect(() => {
    if (importedId !== null && candidatesData !== undefined && candidatesData.items.length === 0) {
      navigate(`/activities/${importedId}`);
    }
  }, [importedId, candidatesData, navigate]);

  function handleFileSelected(selected: File | null) {
    setFile(selected);
    setSportType("");
    setName("");
  }

  function handleImport() {
    if (file === null) {
      return;
    }
    importMutation.mutate(
      {
        file,
        sportType: sportType === "" ? null : sportType,
        name: name.trim() === "" ? null : name.trim(),
      },
      { onSuccess: (activity) => setImportedId(activity.id) },
    );
  }

  function handleLinkAsDuplicate() {
    const primary = selectedPrimary !== "" ? selectedPrimary : candidates[0]?.id;
    if (importedId === null || primary === undefined) {
      return;
    }
    linkMutation.mutate(
      { duplicate_of: primary },
      // Land on the live activity; the new row shows up under its linked duplicates.
      { onSuccess: () => navigate(`/activities/${primary}`) },
    );
  }

  function handleKeepSeparate() {
    if (importedId !== null) {
      navigate(`/activities/${importedId}`);
    }
  }

  // The just-imported row is being checked for duplicates.
  if (importedId !== null && candidates.length === 0) {
    return (
      <div className="mx-auto max-w-xl space-y-6">
        <h1 className="text-xl font-bold text-ink">Upload activity</h1>
        <Card className="p-5 text-sm text-ink-muted">Import complete — checking for duplicates…</Card>
      </div>
    );
  }

  if (importedId !== null && candidates.length > 0) {
    return (
      <div className="mx-auto max-w-xl space-y-6">
        <h1 className="text-xl font-bold text-ink">Upload activity</h1>
        <Card className="space-y-4 p-5">
          <p className="text-sm text-ink-muted">
            This looks like a workout you already have. Pick the one it duplicates — that activity stays live,
            and this import is kept as a linked duplicate (hidden from the feed, still reachable). Or keep it
            separate if they are different efforts.
          </p>

          <div className="space-y-2" role="radiogroup" aria-label="Existing activity this duplicates">
            {candidates.map((candidate) => (
              <label
                key={candidate.id}
                className={`flex cursor-pointer items-center gap-3 rounded-md border px-4 py-3 text-sm transition-colors ${
                  (selectedPrimary !== "" ? selectedPrimary : candidates[0]?.id) === candidate.id
                    ? "border-accent bg-surface"
                    : "border-line hover:border-ink-faint"
                }`}
              >
                <input
                  type="radio"
                  name="duplicate-primary"
                  value={candidate.id}
                  checked={(selectedPrimary !== "" ? selectedPrimary : candidates[0]?.id) === candidate.id}
                  onChange={() => setSelectedPrimary(candidate.id)}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-ink">{candidate.name}</span>
                  <span className="mt-0.5 flex items-center gap-2 text-xs text-ink-muted">
                    <ProviderBadge provider={candidate.provider} />
                    {formatActivityDate(candidate.started_at, timeZone)} ·{" "}
                    {formatClock(candidate.started_at, timeZone)}
                  </span>
                </span>
              </label>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleLinkAsDuplicate}
              disabled={linkMutation.isPending || candidates.length === 0}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
            >
              {linkMutation.isPending ? "Linking…" : "Link as duplicate"}
            </button>
            <button
              type="button"
              onClick={handleKeepSeparate}
              disabled={linkMutation.isPending}
              className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink-muted transition-colors hover:bg-line/40 hover:text-ink disabled:opacity-60"
            >
              Keep as separate activity
            </button>
          </div>

          {linkMutation.isError && <ErrorNote message={linkMutation.error.message} />}
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-xl font-bold text-ink">Upload activity</h1>

      <UploadZone onFileSelected={handleFileSelected} />

      {file !== null && (
        <Card className="space-y-4 p-5">
          <p className="truncate text-sm text-ink-muted">
            <span className="font-medium text-ink">{file.name}</span>
            <span className="ml-2 text-ink-faint">
              {file.size > 0 ? `${(file.size / 1024).toFixed(1)} KB` : ""}
            </span>
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="sport" className="mb-1 block text-sm font-medium text-ink">
                Sport
              </label>
              <select
                id="sport"
                value={sportType}
                onChange={(event) => setSportType(event.target.value)}
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
              >
                <option value="">Detect from file</option>
                {sports.map((sport) => (
                  <option key={sport.value} value={sport.value}>
                    {sport.description}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-ink">
                Title <span className="text-ink-faint">(optional)</span>
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Morning run"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={handleImport}
            disabled={importMutation.isPending}
            className="w-full rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-60"
          >
            {importMutation.isPending ? "Importing…" : "Import activity"}
          </button>

          {importMutation.isError && <ErrorNote message={importMutation.error.message} />}
        </Card>
      )}
    </div>
  );
}
