import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";

export function ForgotPasswordPage() {
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!username.trim()) {
      setError("Enter your assigned username.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/p0/auth/forgot-password", { username: username.trim() });
      setMessage("If an active account with a password exists, a reset token has been issued. Check your email or contact your administrator for the reset link.");
      setUsername("");
    } catch (cause: any) {
      setError(cause?.response?.data?.detail || "Unable to process request. Try again or contact the administrator.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-kfl-canvas px-4 py-10">
      <section className="app-surface w-full max-w-md p-8 shadow-xl" aria-labelledby="forgot-title">
        <img src="/brand/kfl-logo.png" alt="Kenya Flying Labs" className="mx-auto mb-5 h-12 w-auto object-contain" />
        <h1 id="forgot-title" className="text-center text-2xl font-bold text-kfl-text">Forgot password</h1>
        <p className="mb-5 mt-2 text-center text-sm text-kfl-muted">Enter your assigned KFL Aviation DMS username to request a password reset.</p>
        {error && <div role="alert" className="mb-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
        {message && <div role="status" className="mb-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="forgot-username" className="mb-1 block text-sm font-medium">Assigned username</label>
            <input id="forgot-username" name="username" type="text" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required className="app-input w-full" />
          </div>
          <button type="submit" disabled={submitting || !username.trim()} className="app-btn-primary w-full disabled:opacity-60">
            {submitting ? "Sending…" : "Request reset"}
          </button>
        </form>
        <p className="mt-5 text-center text-sm"><Link to="/login" className="text-kfl-blue underline underline-offset-2">Return to sign in</Link></p>
      </section>
    </main>
  );
}
