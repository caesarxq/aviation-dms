import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import api from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { getPostLoginPath } from "../auth/permissions";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [bootstrapConfigured, setBootstrapConfigured] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { state, profile, login } = useAuth();
  const returnTo = (location.state as { from?: string } | null)?.from;

  useEffect(() => {
    let active = true;
    api.get("/p0/auth/bootstrap-status")
      .then(({ data }) => {
        if (active) {
          setSetupRequired(Boolean(data.setup_required));
          setBootstrapConfigured(Boolean(data.bootstrap_configured));
        }
      })
      .catch(() => {
        if (active) setError("Unable to check first-run setup status. Retry or contact the system administrator.");
      });
    return () => { active = false; };
  }, []);

  if (state === "loading") {
    return <main className="app-page min-h-screen"><div role="status" className="app-surface p-10 text-center">Checking secure session…</div></main>;
  }
  if (state === "authenticated") {
    return <Navigate to={getPostLoginPath(profile, returnTo)} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const authenticatedProfile = await login(username.trim(), password);
      setPassword("");
      navigate(getPostLoginPath(authenticatedProfile, returnTo), { replace: true });
    } catch (cause: any) {
      setError(cause?.response?.data?.detail === "Invalid username or password"
        ? "Username or password is incorrect."
        : cause?.response?.data?.detail || "Sign in failed. Try again or contact the administrator.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-kfl-canvas px-4 py-10">
      <section className="app-surface w-full max-w-md p-8 shadow-xl" aria-labelledby="login-title">
        <div className="mb-6 text-center">
          <img src="/brand/kfl-logo.png" alt="Kenya Flying Labs" className="mx-auto mb-5 h-12 w-auto object-contain" />
          <h1 id="login-title" className="text-2xl font-bold text-kfl-text">Secure sign in</h1>
          <p className="mt-2 text-sm text-kfl-muted">Use your assigned KFL Aviation DMS account.</p>
        </div>

        {error && <div role="alert" className="mb-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4" autoComplete="on">
          <div>
            <label htmlFor="login-username" className="mb-1 block text-sm font-medium text-kfl-text">Username</label>
            <input id="login-username" name="username" type="text" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required className="app-input w-full" />
          </div>
          <div className="relative">
            <label htmlFor="login-password" className="mb-1 block text-sm font-medium text-kfl-text">Password</label>
            <input
              id="login-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              className="app-input w-full pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2 top-1/2 -mt-2 text-kfl-muted hover:text-kfl-text"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
          <button type="submit" disabled={submitting || !username.trim() || !password} className="app-btn-primary w-full disabled:cursor-not-allowed disabled:opacity-60">
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-3 text-center text-sm"><Link to="/forgot-password" className="text-kfl-blue underline underline-offset-2">Forgot password?</Link></p>

        {setupRequired && (
          <div className="mt-5 border-t border-kfl-border pt-4 text-sm">
            {bootstrapConfigured ? (
              <Link to="/setup" className="font-medium text-kfl-blue underline underline-offset-2">Set the initial administrator password</Link>
            ) : (
              <p role="status" className="text-kfl-muted">First-run setup is not enabled. Ask the deployment administrator to configure the bootstrap token.</p>
            )}
          </div>
        )}
        <p className="mt-5 text-center text-xs text-kfl-muted">Access is role-scoped and audited. Contact the system administrator if you need an account or a different access profile.</p>
      </section>
    </main>
  );
}

