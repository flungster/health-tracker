import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { AuthShell, FieldError, inputClass, labelClass, LinkLine, PrimaryButton } from "../components/AuthShell";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell title="Sign in" subtitle="Welcome back to your training.">
      <form onSubmit={handleSubmit} noValidate={false}>
        <div className="space-y-4">
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
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClass(false)}
              placeholder="••••••••"
            />
          </div>
        </div>
        <FieldError error={error} />
        <div className="mt-5">
          <PrimaryButton disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </PrimaryButton>
        </div>
      </form>
      <LinkLine to="/register" text="Create an account">New here?</LinkLine>
    </AuthShell>
  );
}
