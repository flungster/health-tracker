import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { AuthShell, FieldError, inputClass, labelClass, LinkLine, PrimaryButton } from "../components/AuthShell";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({
        first_name: firstName,
        last_name: lastName,
        email,
        password,
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Start tracking your activities.">
      <form onSubmit={handleSubmit} noValidate={false}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="first-name" className={labelClass()}>First name</label>
              <input
                id="first-name"
                type="text"
                autoComplete="given-name"
                required
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
                className={inputClass(false)}
              />
            </div>
            <div>
              <label htmlFor="last-name" className={labelClass()}>Last name</label>
              <input
                id="last-name"
                type="text"
                autoComplete="family-name"
                required
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
                className={inputClass(false)}
              />
            </div>
          </div>
          <div>
            <label htmlFor="email" className={labelClass()}>Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClass(false)}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label htmlFor="password" className={labelClass()}>Password</label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClass(false)}
              placeholder="At least 8 characters"
            />
          </div>
        </div>
        <FieldError error={error} />
        <div className="mt-5">
          <PrimaryButton disabled={submitting}>
            {submitting ? "Creating account…" : "Create account"}
          </PrimaryButton>
        </div>
      </form>
      <LinkLine to="/login" text="Sign in">Already have an account?</LinkLine>
    </AuthShell>
  );
}
