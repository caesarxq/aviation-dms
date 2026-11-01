import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";

export function ResetPasswordPage() {
  const [resetToken, setResetToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { token } = useParams<{ token?: string }>();

  useEffect(() => {
    if (token) setResetToken(token);
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!resetToken) {
      setError("Missing reset token.");
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
      await api.post("/p0/auth/reset-password", { reset_token: resetToken, password });
      setMessage("Password reset. Sign in with your new password.");
      setPassword("");
      setConfirmPassword("");
    } catch (cause: any) {
      setError(cause?.response?.data?.detail || "Invalid or expired reset token.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-kfl-canvas px-4 py-10">
      <section className="app-surface w-full max-w-md p-8 shadow-xl" aria-labelledby="reset-title">
        <img src="/brand/kfl-logo.png" alt="Kenya Flying Labs" className="mx-auto mb-5 h-12 w-auto object-contain" />
        <h1 id="reset-title" className="text-center text-2xl font-bold text-kfl-text">Reset password</h1>
        <p className="mb-5 mt-2 text-center text-sm text-kfl-muted">Enter your new password using the reset token sent to you.</p>
        {error && <div role="alert" className="mb-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
        {message && <div role="status" className="mb-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="reset-token" className="mb-1 block text-sm font-medium">Reset token</label>
            <input id="reset-token" name="reset_token" type="password" autoComplete="off" value={resetToken} onChange={(event) => setResetToken(event.target.value)} required className="app-input w-full" />
          </div>
          <div>
            <label htmlFor="reset-password" className="mb-1 block text-sm font-medium">New password</label>
            <input id="reset-password" name="new_password" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} className="app-input w-full" />
          </div>
          <div>
            <label htmlFor="reset-password-confirm" className="mb-1 block text-sm font-medium">Confirm new password</label>
            <input id="reset-password-confirm" name="confirm_password" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required minLength={12} className="app-input w-full" />
          </div>
          <button type="submit" disabled={submitting} className="app-btn-primary w-full disabled:opacity-60">
            {submitting ? "Resetting…" : "Reset password"}
          </button>
        </form>
        <p className="mt-5 text-center text-sm"><Link to="/login" className="text-kfl-blue underline underline-offset-2">Return to sign in</Link></p>
      </section>
    </main>
  );
}
