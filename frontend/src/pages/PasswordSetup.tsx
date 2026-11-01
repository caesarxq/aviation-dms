import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import api from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { getPostLoginPath } from "../auth/permissions";

type BootstrapStatus = { setup_required: boolean; bootstrap_configured: boolean; bootstrap_token_required: boolean };

export function PasswordSetupPage() {
  const [status, setStatus] = useState<BootstrapStatus | null>(null);
  const [username, setUsername] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [statusRetry, setStatusRetry] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const { state: authState, profile, refreshProfile } = useAuth();

  const inviteFromUrl = (location.pathname.match(/\/setup\/invite\/([A-Za-z0-9-]+)/) || [])[1];
  const isInviteMode = Boolean(inviteFromUrl);
  const initialSetup = Boolean(status?.setup_required);

  useEffect(() => {
    let active = true;
    if (!isInviteMode) {
      api.get("/p0/auth/bootstrap-status")
        .then(({ data }) => { if (active) setStatus(data as BootstrapStatus); })
        .catch(() => { if (active) setError("Unable to determine whether initial setup is available."); });
    }
    return () => { active = false; };
  }, [statusRetry, isInviteMode]);

  if (authState === "loading") {
    return <main className="app-page min-h-screen"><div role="status" className="app-surface p-10 text-center">Checking secure session…</div></main>;
  }
  if (authState === "authenticated") return <Navigate to={getPostLoginPath(profile)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!isInviteMode && !initialSetup && !username.trim()) {
      setError("Enter your assigned username.");
      return;
    }
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    if (password.length < 12 || new TextEncoder().encode(password).length > 72) {
      setError("Use a password of at least 12 characters and no more than 72 UTF-8 bytes.");
      return;
    }
    setSubmitting(true);
    try {
      if (isInviteMode) {
        await api.post("/p0/auth/password-setup", { invite_code: inviteFromUrl, password });
        setMessage("Password set. Sign in with your assigned username and new password.");
        setPassword("");
        setConfirmPassword("");
      } else if (initialSetup) {
        await api.post("/p0/auth/bootstrap", { bootstrap_token: token || null, password });
        const authenticatedProfile = await refreshProfile();
        navigate(getPostLoginPath(authenticatedProfile), { replace: true });
      } else {
        await api.post("/p0/auth/password-setup", { username: username.trim(), setup_token: token, password });
        setMessage("Password set. Sign in with your assigned username and new password.");
        setPassword("");
        setConfirmPassword("");
        setToken("");
      }
    } catch (cause: any) {
      setError(cause?.response?.data?.detail || "Password setup failed. Check the one-time token or contact the administrator.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!status && !isInviteMode) {
    return (
      <main className="app-page min-h-screen">
        <div className="app-surface p-10 text-center">
          {error ? (
            <>
              <p role="alert" className="text-sm text-rose-800">{error}</p>
              <button
                type="button"
                onClick={() => { setError(""); setStatus(null); setStatusRetry((attempt) => attempt + 1); }}
                className="app-btn-secondary mt-4"
              >
                Retry
              </button>
            </>
          ) : (
            <div role="status">Checking account setup…</div>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-kfl-canvas px-4 py-10">
      <section className="app-surface w-full max-w-md p-8 shadow-xl" aria-labelledby="setup-title">
        <img src="/brand/kfl-logo.png" alt="Kenya Flying Labs" className="mx-auto mb-5 h-12 w-auto object-contain" />
        <h1 id="setup-title" className="text-center text-2xl font-bold text-kfl-text">
          {isInviteMode ? "Set your account password" : initialSetup ? "Initial administrator setup" : "Set your account password"}
        </h1>
        <p className="mb-5 mt-2 text-center text-sm text-kfl-muted">
          {isInviteMode
            ? "Use your invite code to set your password. Your username is already filled in."
            : initialSetup
            ? "Create the first administrator password using the one-time deployment token."
            : "Use the one-time setup token supplied by your administrator."}
        </p>
        {error && <div role="alert" className="mb-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
        {message && <div role="status" className="mb-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
        {initialSetup && !status?.bootstrap_configured && <p role="alert" className="mb-4 text-sm text-rose-800">Bootstrap is disabled. Configure the server-side KFL_BOOTSTRAP_TOKEN first.</p>}
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isInviteMode && !initialSetup && !status?.setup_required && (
            <div>
              <label htmlFor="setup-username" className="mb-1 block text-sm font-medium">Assigned username</label>
              <input id="setup-username" name="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required className="app-input w-full" />
            </div>
          )}
          {!isInviteMode && (
            <div>
              <label htmlFor="setup-token" className="mb-1 block text-sm font-medium">{initialSetup ? "Bootstrap token" : "One-time setup token"}</label>
              <input id="setup-token" name="setup_token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required={initialSetup ? status?.bootstrap_token_required : true} className="app-input w-full" />
            </div>
          )}
          <div>
            <label htmlFor="setup-password" className="mb-1 block text-sm font-medium">New password</label>
            <input id="setup-password" name="new_password" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} className="app-input w-full" />
          </div>
          <div>
            <label htmlFor="setup-password-confirm" className="mb-1 block text-sm font-medium">Confirm new password</label>
            <input id="setup-password-confirm" name="confirm_password" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required minLength={12} className="app-input w-full" />
          </div>
          <button type="submit" disabled={submitting || (initialSetup && !status?.bootstrap_configured)} className="app-btn-primary w-full disabled:opacity-60">
            {submitting ? "Saving…" : "Set password"}
          </button>
        </form>
        <p className="mt-5 text-center text-sm"><Link to="/login" className="text-kfl-blue underline underline-offset-2">Return to sign in</Link></p>
      </section>
    </main>
  );
}
