/** Profile: account info, heart-rate settings, and password change. */

import { useEffect, useState, type FormEvent } from "react";

import { useProfile, useUpdateProfile, useUpdateUser } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { Card, ErrorNote, Spinner } from "../components/Ui";
import { inputClass, labelClass } from "../components/AuthShell";
import { formatActivityDate } from "../format";

export default function ProfilePage() {
  const { user } = useAuth();
  const { data: profile, isPending } = useProfile();
  const profileMutation = useUpdateProfile();
  const userMutation = useUpdateUser();

  const [maxHr, setMaxHr] = useState<string>("");
  const [restingHr, setRestingHr] = useState<string>("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    if (profile === undefined) {
      return;
    }
    setMaxHr(profile.max_heart_rate?.toString() ?? "");
    setRestingHr(profile.resting_heart_rate?.toString() ?? "");
  }, [profile]);

  if (isPending) {
    return <Spinner label="Loading profile…" />;
  }

  function handleProfileSubmit(event: FormEvent) {
    event.preventDefault();
    profileMutation.mutate({
      max_heart_rate: maxHr === "" ? null : Number(maxHr),
      resting_heart_rate: restingHr === "" ? null : Number(restingHr),
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

      <Card className="p-5">
        <h2 className="text-base font-semibold text-ink">Heart-rate zones</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Used to compute zone splits for imported activities.
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
