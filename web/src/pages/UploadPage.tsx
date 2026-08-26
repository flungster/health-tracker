/** Import a GPX/TCX/FIT file, with optional sport and name overrides. */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useImportActivity, useSports } from "../api/hooks";
import UploadZone from "../components/UploadZone";
import { Card, ErrorNote } from "../components/Ui";

export default function UploadPage() {
  const navigate = useNavigate();
  const { data: sportsData } = useSports();
  const importMutation = useImportActivity();

  const [file, setFile] = useState<File | null>(null);
  const [sportType, setSportType] = useState<string>("");
  const [name, setName] = useState<string>("");

  const sports = sportsData?.sports ?? [];

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
      {
        onSuccess: (activity) => {
          navigate(`/activities/${activity.id}`);
        },
      },
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

          {importMutation.isError && (
            <ErrorNote message={importMutation.error.message} />
          )}
        </Card>
      )}
    </div>
  );
}
