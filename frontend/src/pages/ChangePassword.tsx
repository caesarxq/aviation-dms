import { useState, type FormEvent } from "react";
import api from "../api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
      return;
    }
    if (newPassword.length < 12 || new TextEncoder().encode(newPassword).length > 72) {
      setError("Use a password of at least 12 characters and no more than 72 UTF-8 bytes.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/p0/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setMessage("Password changed. Other active sessions have been signed out.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (cause: any) {
      setError(cause?.response?.data?.detail || "Password change failed. Try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="app-page max-w-2xl">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Account security</div>
          <h1 className="app-title">Change password</h1>
          <p className="app-subtitle">Changing your password signs out other active sessions.</p>
        </div>
      </header>
      <section className="app-surface p-6">
        {error && <div role="alert" className="mb-4 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger p-3 text-sm">{error}</div>}
        {message && <div role="status" className="mb-4 rounded-md border border-kfl-status-success-bg bg-kfl-status-success-bg/20 text-kfl-status-success p-3 text-sm">{message}</div>}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="current-password" className="mb-1 block text-sm font-medium">Current password</label>
            <Input id="current-password" name="current_password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required className="w-full" />
          </div>
          <div>
            <label htmlFor="new-password" className="mb-1 block text-sm font-medium">New password</label>
            <Input id="new-password" name="new_password" type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required className="w-full" />
          </div>
          <div>
            <label htmlFor="confirm-new-password" className="mb-1 block text-sm font-medium">Confirm new password</label>
            <Input id="confirm-new-password" name="confirm_new_password" type="password" autoComplete="new-password" minLength={12} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required className="w-full" />
          </div>
          <Button type="submit" disabled={saving} className="w-full disabled:opacity-60">{saving ? "Saving…" : "Change password"}</Button>
        </form>
      </section>
    </div>
  );
}
