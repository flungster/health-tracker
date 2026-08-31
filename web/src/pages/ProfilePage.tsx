/** Profile: account info, connected accounts, heart-rate settings, password. */

import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { useProfile, useUpdateProfile, useUpdateUser } from "../api/hooks";
import type { ProfileView } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import ConnectedAccounts from "../components/ConnectedAccounts";
import { Card, ErrorNote, Spinner } from "../components/Ui";
import { inputClass, labelClass } from "../components/AuthShell";
import { capitalize, formatActivityDate } from "../format";

function connectFailureReason(reason: string | null): string {
  switch (reason) {
    case "denied":
      return "you declined the authorization.";
    case "state":
      return "the attempt expired or was interrupted. Try connecting again.";
    default:
      return "the provider could not complete the connection. Try again.";
  }
}

/** One line naming the zone reference currently in effect (from the API). */
function zoneReferenceText(profile: ProfileView | undefined): string {
  if (profile === undefined) {
    return "";
  }
  switch (profile.zone_source) {
    case "custom":
      return `Zones are computed from your custom boundaries (${profile.custom_zone_1_top_bpm ?? "–"} / ${
        profile.custom_zone_2_top_bpm ?? "–"
      } / ${profile.custom_zone_3_top_bpm ?? "–"} / ${profile.custom_zone_4_top_bpm ?? "–"} bpm).`;
    case "max_heart_rate":
      return `Zones are computed from your max heart rate (${profile.effective_max_heart_rate ?? "–"} bpm).`;
    case "age":
      return `Zones are computed from your date of birth — max heart rate ${profile.effective_max_heart_rate ?? "–"} bpm (220 − your age, currently ${
        profile.age ?? "?"
      }).`;
    default:
      return "No zone reference is set yet — activity heart-rate zones stay hidden.";
  }
}

export default function ProfilePage() {
  const { user } = useAuth();
  const { data: profile, isPending } = useProfile();
  const profileMutation = useUpdateProfile();
  const userMutation = useUpdateUser();
  const [searchParams, setSearchParams] = useSearchParams();

  // One-shot OAuth results (?connected= / ?connect_error=) from the provider
  // callback redirect: report them, then clear so a re-render can't re-report.
  const connectedProvider = searchParams.get("connected");
  const connectErrorProvider = searchParams.get("connect_error");
  const connectReason = searchParams.get("reason");
  useEffect(() => {
    if (connectedProvider === null && connectErrorProvider === null) {
      return;
    }
    setSearchParams({}, { replace: true });
  }, [connectedProvider, connectErrorProvider, setSearchParams]);

  const [maxHr, setMaxHr] = useState<string>("");
  const [restingHr, setRestingHr] = useState<string>("");
  const [dateOfBirth, setDateOfBirth] = useState<string>(""); // "YYYY-MM-DD"
  const [customZone1, setCustomZone1] = useState<string>("");
  const [customZone2, setCustomZone2] = useState<string>("");
  const [customZone3, setCustomZone3] = useState<string>("");
  const [customZone4, setCustomZone4] = useState<string>("");

  // Client-side error for the custom-zone completeness/ascending rule (the
  // server re-validates everything and owns the final error envelope).
  const [zoneFormError, setZoneFormError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    if (profile === undefined) {
      return;
    }
    setMaxHr(profile.max_heart_rate?.toString() ?? "");
    setRestingHr(profile.resting_heart_rate?.toString() ?? "");
    setDateOfBirth(profile.date_of_birth ?? "");
    setCustomZone1(profile.custom_zone_1_top_bpm?.toString() ?? "");
    setCustomZone2(profile.custom_zone_2_top_bpm?.toString() ?? "");
    setCustomZone3(profile.custom_zone_3_top_bpm?.toString() ?? "");
    setCustomZone4(profile.custom_zone_4_top_bpm?.toString() ?? "");
  }, [profile]);

  if (isPending) {
    return <Spinner label="Loading profile…" />;
  }

  function handleProfileSubmit(event: FormEvent) {
    event.preventDefault();

    // Custom zones are all-or-nothing on the server, so check that rule here
    // for a friendlier error than a 422.
    const zoneTops: [string, string, string, string] = [
      customZone1,
      customZone2,
      customZone3,
      customZone4,
    ];
    const filled = zoneTops.filter((top) => top !== "").length;

    let customTops: [number | null, number | null, number | null, number | null];
    if (filled === 0) {
      customTops = [null, null, null, null]; // all blank clears the set
    } else if (filled < 4) {
      setZoneFormError("Enter all four custom zone tops, or leave them all blank.");
      return;
    } else {
      const parsed: [number, number, number, number] = [
        Number(zoneTops[0]),
        Number(zoneTops[1]),
        Number(zoneTops[2]),
        Number(zoneTops[3]),
      ];
      if (parsed.some((top) => !Number.isInteger(top))) {
        setZoneFormError("Custom zone tops must be whole numbers (bpm).");
        return;
      }
      if (parsed.some((top) => top < 30 || top > 300)) {
        setZoneFormError("Custom zone tops must be between 30 and 300 bpm.");
        return;
      }
      if (!(parsed[0] < parsed[1]) || !(parsed[1] < parsed[2]) || !(parsed[2] < parsed[3])) {
        setZoneFormError("Custom zone tops must be strictly ascending (zone 1 lowest).");
        return;
      }
      customTops = [parsed[0], parsed[1], parsed[2], parsed[3]];
    }

    setZoneFormError(null);
    profileMutation.mutate({
      max_heart_rate: maxHr === "" ? null : Number(maxHr),
      resting_heart_rate: restingHr === "" ? null : Number(restingHr),
      date_of_birth: dateOfBirth === "" ? null : dateOfBirth,
      custom_zone_1_top_bpm: customTops[0],
      custom_zone_2_top_bpm: customTops[1],
      custom_zone_3_top_bpm: customTops[2],
      custom_zone_4_top_bpm: customTops[3],
    });
  }

  function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault();
    userMutation.mutate({
      first_name: null,
      last_name: null,
      email: null,
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-xl font-bold text-ink">Profile</h1>

      {connectedProvider !== null && (
        <div className="rounded-md border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-accent-dark">
          {capitalize(connectedProvider)} connected.
        </div>
      )}
      {connectErrorProvider !== null && (
        <ErrorNote
          message={`${capitalize(connectErrorProvider)} connection failed: ${connectFailureReason(connectReason)}`}
        />
      )}

      <Card className="p-5">
        <h2 className="text-base font-semibold text-ink">Account</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-ink-muted">Name</dt>
            <dd className="font-medium text-ink">
              {user !== null ? `${user.first_name} ${user.last_name}`.trim() : "—"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-muted">Email</dt>
            <dd className="font-medium text-ink">{user?.email ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-muted">Member since</dt>
            <dd className="font-medium text-ink">
              {user !== null ? formatActivityDate(user.created_at) : "—"}
            </dd>
          </div>
        </dl>
      </Card>

      <ConnectedAccounts />

      <Card className="p-5">
        <h2 className="text-base font-semibold text-ink">Heart-rate zones</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Used to compute zone splits for imported activities.
        </p>
        <p className="mt-2 text-sm font-medium text-accent-dark">
          {zoneReferenceText(profile)}
        </p>
        <form onSubmit={handleProfileSubmit} className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="max-hr" className={labelClass()}>Max heart rate</label>
              <input
                id="max-hr"
                type="number"
                min={1}
                value={maxHr}
                onChange={(event) => setMaxHr(event.target.value)}
                className={inputClass(false)}
                placeholder="190"
              />
            </div>
            <div>
              <label htmlFor="resting-hr" className={labelClass()}>Resting heart rate</label>
              <input
                id="resting-hr"
                type="number"
                min={1}
                value={restingHr}
                onChange={(event) => setRestingHr(event.target.value)}
                className={inputClass(false)}
                placeholder="60"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="date-of-birth" className={labelClass()}>Date of birth</label>
            <input
              id="date-of-birth"
              type="date"
              value={dateOfBirth}
              onChange={(event) => setDateOfBirth(event.target.value)}
              className={inputClass(false)}
            />
            <p className="text-xs text-ink-muted">
              Optional fallback: with no custom zones and no max heart rate, your age sets the
              reference (max HR = 220 − age).
            </p>
          </div>

          <fieldset className="space-y-2">
            <legend className={labelClass()}>Custom zone boundaries</legend>
            <p className="text-xs text-ink-muted">
              Optional. When all four are set they take priority over the max heart rate: zone 1
              is at or below its top, and so on — zone 5 above the fourth. Leave all blank to
              clear them.
            </p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {(
                [
                  ["cz-top-1", customZone1, setCustomZone1, "Zone 1 top"],
                  ["cz-top-2", customZone2, setCustomZone2, "Zone 2 top"],
                  ["cz-top-3", customZone3, setCustomZone3, "Zone 3 top"],
                  ["cz-top-4", customZone4, setCustomZone4, "Zone 4 top"],
                ] as const
              ).map(([id, value, setValue, label]) => (
                <div key={id}>
                  <label htmlFor={id} className={labelClass()}>
                    {label}
                  </label>
                  <input
                    id={id}
                    type="number"
                    min={30}
                    max={300}
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    className={inputClass(false)}
                  />
                </div>
              ))}
            </div>
          </fieldset>

          {zoneFormError !== null && <ErrorNote message={zoneFormError} />}
          <button
            type="submit"
            disabled={profileMutation.isPending}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
          >
            {profileMutation.isPending ? "Saving…" : "Save settings"}
          </button>
          {profileMutation.isError && (
            <ErrorNote message={profileMutation.error.message} />
          )}
          {profileMutation.isSuccess && (
            <p className="text-sm text-accent-dark">Saved.</p>
          )}
        </form>
      </Card>

      <Card className="p-5">
        <h2 className="text-base font-semibold text-ink">Change password</h2>
        <form onSubmit={handlePasswordSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="current-password" className={labelClass()}>Current password</label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              className={inputClass(false)}
            />
          </div>
          <div>
            <label htmlFor="new-password" className={labelClass()}>New password</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className={inputClass(false)}
            />
          </div>
          <button
            type="submit"
            disabled={userMutation.isPending}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
          >
            {userMutation.isPending ? "Updating…" : "Update password"}
          </button>
          {userMutation.isError && <ErrorNote message={userMutation.error.message} />}
          {userMutation.isSuccess && (
            <p className="text-sm text-accent-dark">Password updated.</p>
          )}
        </form>
      </Card>
    </div>
  );
}
