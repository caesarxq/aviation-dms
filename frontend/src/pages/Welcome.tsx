import { useEffect, useState } from "react";
import { Navigate, Link, useNavigate } from "react-router-dom";
import api from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { getPostLoginPath } from "../auth/permissions";

export function WelcomePage() {
  const [onboarding, setOnboarding] = useState<{
    onboarding_completed: boolean;
    assigned_roles: string[];
    active_role: string;
    canonical_user_id: string;
    full_name: string;
    email: string;
    department: string | null;
  } | null>(null);
  const [profileEdits, setProfileEdits] = useState<{ email: string; department: string }>({
    email: "",
    department: "",
  });
  const [editsPending, setEditsPending] = useState(false);
  const [selectedRole, setSelectedRole] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { profile, refreshProfile } = useAuth();

  useEffect(() => {
    let active = true;
    api.get("/p0/auth/me/onboarding")
      .then(({ data }) => {
        if (active) {
          setOnboarding(data as any);
          setSelectedRole(data.active_role);
          setProfileEdits({ email: data.email ?? "", department: data.department ?? "" });
        }
      })
      .catch(() => {
        if (active) setError("Unable to load your onboarding information.");
      });
    return () => { active = false; };
  }, []);

  if (!onboarding) {
    return <main className="app-page min-h-screen"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading your welcome screen…</div></main>;
  }

  if (onboarding.onboarding_completed) {
    return <Navigate to={getPostLoginPath(profile)} replace />;
  }

  async function handleSaveProfile() {
    if (!onboarding) return;
    setEditsPending(true);
    try {
      const updates: Record<string, string> = {};
      if (profileEdits.email !== onboarding.email) updates.email = profileEdits.email;
      if (profileEdits.department !== (onboarding.department ?? "")) updates.department = profileEdits.department;
      if (Object.keys(updates).length > 0) {
        await api.put("/p0/auth/me/profile", updates);
      }
      await api.post("/p0/auth/me/onboarding/complete");
      const completedProfile = await refreshProfile();
      navigate(getPostLoginPath(completedProfile), { replace: true });
    } catch (cause: any) {
      setEditsPending(false);
      setError(cause?.response?.data?.detail || "Unable to save profile corrections. Try again.");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-kfl-canvas px-4 py-10">
      <section className="app-surface w-full max-w-md p-8 shadow-xl" aria-labelledby="welcome-title">
        <img src="/brand/kfl-logo.png" alt="Kenya Flying Labs" className="mx-auto mb-5 h-12 w-auto object-contain" />
        <h1 id="welcome-title" className="text-center text-2xl font-bold text-kfl-text">Welcome to KFL Aviation DMS</h1>
        <p className="mb-5 text-center text-sm text-kfl-muted">Let's confirm your access profile before you start.</p>
        <div className="space-y-4">
          <div className="bg-kfl-surface-subtle rounded p-4">
            <p className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Name</p>
            <p className="text-sm text-kfl-text">{onboarding.full_name || profile?.user.full_name || "Not listed"}</p>
          </div>
          <div className="bg-kfl-surface-subtle rounded p-4">
            <p className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Canonical ID</p>
            <p className="text-sm font-mono text-kfl-text">{onboarding.canonical_user_id}</p>
          </div>
          <div className="bg-kfl-surface-subtle rounded p-4">
            <div className="flex flex-col gap-2">
              <label htmlFor="welcome-email" className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Email</label>
              <input
                id="welcome-email"
                type="email"
                value={profileEdits.email}
                onChange={(e) => setProfileEdits({ ...profileEdits, email: e.target.value })}
                className="w-full rounded border border-kfl-border bg-white px-2 py-1 text-xs text-kfl-text"
                placeholder={onboarding.email || "Not listed"}
              />
              <p className="text-[10px] text-kfl-muted">Confirm or correct your email address.</p>
            </div>
          </div>
          <div className="bg-kfl-surface-subtle rounded p-4">
            <div className="flex flex-col gap-2">
              <label htmlFor="welcome-department" className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Department</label>
              <input
                id="welcome-department"
                type="text"
                value={profileEdits.department}
                onChange={(e) => setProfileEdits({ ...profileEdits, department: e.target.value })}
                className="w-full rounded border border-kfl-border bg-white px-2 py-1 text-xs text-kfl-text"
                placeholder={onboarding.department || "Not listed"}
              />
              <p className="text-[10px] text-kfl-muted">Confirm or correct your department.</p>
            </div>
          </div>
          <div className="bg-kfl-surface-subtle rounded p-4">
            <p className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Your assigned roles</p>
            <ul className="text-sm text-kfl-text space-y-1">
              {onboarding.assigned_roles.map((role) => (
                <li key={role} className="flex items-center gap-2">
                  <span className="text-kfl-blue">{role.replace(/_/g, " ")}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <label htmlFor="welcome-active-role" className="mb-1 block text-sm font-medium">Active role for this session</label>
            <p className="text-xs text-kfl-muted mb-2">Each session uses one assigned role. Your permissions are scoped to this role.</p>
            <select
              id="welcome-active-role"
              value={selectedRole}
              onChange={(event) => setSelectedRole(event.target.value)}
              className="w-full rounded border border-kfl-border bg-white px-2 py-1.5 text-xs text-kfl-text"
            >
              {onboarding.assigned_roles.map((role) => (
                <option key={role} value={role}>{role.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          {error && <div role="alert" className="mb-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
          {editsPending ? (
            <button type="button" disabled className="app-btn-primary w-full opacity-60">Saving profile…</button>
          ) : (
            <button
              type="button"
              onClick={handleSaveProfile}
              className="app-btn-primary w-full disabled:opacity-60"
            >
              Save corrections & continue
            </button>
          )}
        </div>
        <p className="mt-5 text-center text-sm"><Link to="/login" className="text-kfl-blue underline underline-offset-2">Return to sign in</Link></p>
      </section>
    </main>
  );
}
