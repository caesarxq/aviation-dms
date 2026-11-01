import { useEffect, useState, type FormEvent } from "react";
import api from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function ProfileSettingsPage() {
  const [profile, setProfile] = useState<{
    user_id: string;
    username: string;
    email: string;
    full_name: string;
    role: string;
    active_role: string;
    roles: string[];
    department: string | null;
    onboarding_completed: boolean;
  } | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { refreshProfile } = useAuth();

  useEffect(() => {
    let active = true;
    api.get("/p0/auth/profile")
      .then(({ data }) => {
        if (active) setProfile(data as any);
      })
      .catch(() => {
        if (active) setError("Unable to load your profile.");
      });
    return () => { active = false; };
  }, []);

  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (newPassword !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    if (newPassword.length < 12 || new TextEncoder().encode(newPassword).length > 72) {
      setError("Password must be at least 12 characters and no more than 72 UTF-8 bytes.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/p0/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setMessage("Password changed successfully. Your other sessions were signed out.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      await refreshProfile();
    } catch (cause: any) {
      setError(cause?.response?.data?.detail || "Password change failed. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!profile) {
    return (
      <main className="app-page min-h-screen">
        <div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading profile settings…</div>
      </main>
    );
  }

  return (
    <main className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Account</div>
          <h1 className="app-title">Profile Settings</h1>
          <p className="app-subtitle">Manage your account profile and security settings.</p>
        </div>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Canonical ID</div><span className="font-mono text-sm text-kfl-text">{profile.user_id}</span></div></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Username</div><span className="text-sm text-kfl-text">{profile.username}</span></div></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Email</div><span className="text-sm text-kfl-text">{profile.email}</span></div></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Full Name</div><span className="text-sm text-kfl-text">{profile.full_name}</span></div></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Department</div><span className="text-sm text-kfl-text">{profile.department || "—"}</span></div></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Roles</div><span className="text-sm text-kfl-text">{profile.roles.map((r) => r.replace(/_/g, " ")).join(", ")}</span></div></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Active Role</div><span className="text-sm text-kfl-text">{profile.active_role.replace(/_/g, " ")}</span></div></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Onboarding</div><span className={`text-sm font-medium ${profile.onboarding_completed ? "text-emerald-600" : "text-rose-600"}`}>{profile.onboarding_completed ? "Complete" : "Pending"}</span></div></div>
      </section>

      <section className="mb-6 app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Change Password</h2><p className="mt-1 text-xs text-kfl-muted">Update your account password.</p></div>
        {error && <div role="alert" className="m-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
        {message && <div role="status" className="m-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
        <form onSubmit={handlePasswordChange} className="m-6 space-y-4">
          <div>
            <label htmlFor="profile-current-password" className="mb-1 block text-sm font-medium text-kfl-text">Current Password</label>
            <input id="profile-current-password" name="current_password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required className="app-input w-full" />
          </div>
          <div>
            <label htmlFor="profile-new-password" className="mb-1 block text-sm font-medium text-kfl-text">New Password</label>
            <input id="profile-new-password" name="new_password" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required minLength={12} className="app-input w-full" />
          </div>
          <div>
            <label htmlFor="profile-confirm-password" className="mb-1 block text-sm font-medium text-kfl-text">Confirm New Password</label>
            <input id="profile-confirm-password" name="confirm_password" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required minLength={12} className="app-input w-full" />
          </div>
          <button type="submit" disabled={submitting} className="app-btn-primary w-full disabled:opacity-60">
            {submitting ? "Changing…" : "Change Password"}
          </button>
        </form>
      </section>

      <section className="mb-6 app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Signed In As</h2></div>
        <div className="p-6">
          <p className="text-sm text-kfl-text">{profile.full_name}</p>
          <p className="text-xs text-kfl-muted">{profile.user_id} · {profile.username} · {profile.email}</p>
        </div>
      </section>
    </main>
  );
}
