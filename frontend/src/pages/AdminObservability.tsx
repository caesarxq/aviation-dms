import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { Activity, Database, Mail, RefreshCw, ShieldCheck, Users } from "lucide-react";
import api from "../api/client";

function StatusPill({ ok, children }: { ok: boolean; children: ReactNode }) {
  return <span className={`app-status ${ok ? "app-status-healthy" : "app-status-critical"}`}>{children}</span>;
}

export default function AdminObservability() {
  const queryClient = useQueryClient();
  const [roleDrafts, setRoleDrafts] = useState<Record<string, string[]>>({});
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [inviteUsername, setInviteUsername] = useState("");
  const [inviteRoles, setInviteRoles] = useState<string[]>([]);
  const [invitingUserId, setInvitingUserId] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState("");
  const [inviteNotice, setInviteNotice] = useState("");
  const [issuedInvites, setIssuedInvites] = useState<{ user_id: string; full_name: string; invite_code: string; setup_url: string }[]>([]);
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["admin-observability"],
    queryFn: () => api.get("/p0/admin/observability").then((response: any) => response.data),
    refetchInterval: 30000,
  });

  async function saveRoles(user: any) {
    const roles = roleDrafts[user.user_id] ?? user.roles ?? [user.role];
    if (roles.length === 0) {
      return;
    }
    setSavingUserId(user.user_id);
    try {
      await api.put(`/p0/auth/users/${encodeURIComponent(user.user_id)}/roles`, { roles });
      setRoleDrafts((current) => {
        const next = { ...current };
        delete next[user.user_id];
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
    } catch (cause: any) {
      // Error will be shown by the invalidated query refetch
    } finally {
      setSavingUserId(null);
    }
  }

  async function handleInvite() {
    setInviteError("");
    setInviteNotice("");
    if (!inviteUsername.trim()) {
      setInviteError("Enter a username.");
      return;
    }
    setInvitingUserId(inviteUsername.trim());
    try {
      const inviteResponse = await api.post("/p0/auth/invites", { username: inviteUsername.trim(), roles: inviteRoles.length > 0 ? inviteRoles : undefined });
      setIssuedInvites((prev) => [...prev, {
        user_id: inviteResponse.data?.user_id || inviteUsername.trim(),
        full_name: inviteResponse.data?.full_name || inviteUsername.trim(),
        invite_code: inviteResponse.data.invite_code,
        setup_url: inviteResponse.data.setup_url,
      }]);
      setInviteNotice(`Invite issued for ${inviteUsername.trim()}. Share the code securely with the user.`);
      setInviteUsername("");
      setInviteRoles([]);
      await queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
    } catch (cause: any) {
      setInviteError(cause?.response?.data?.detail || "Unable to issue invite. Retry or check administrator access.");
    } finally {
      setInvitingUserId(null);
    }
  }

  if (isLoading) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading system observability…</div></div>;
  if (isError) {
    const status = (error as any)?.response?.status;
    return <div className="app-page"><div className="app-surface border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800">{status === 403 ? "System administrator access is required." : "Unable to load observability data."}</div></div>;
  }

  const dbOk = data?.database?.status === "ok";
  const healthOk = data?.health?.status === "ok";
  const workflowCounts = data?.workflows?.document_versions || {};

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Administration</div>
          <h1 className="app-title">System Observability</h1>
          <p className="app-subtitle">System health, workflow posture, audit activity, and administrator-controlled access profiles.</p>
        </div>
        <button className="app-btn-secondary" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} /> Refresh
        </button>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">API health</div><Activity className="text-emerald-600" size={20} /></div><div className="mt-3"><StatusPill ok={healthOk}>{healthOk ? "Healthy" : "Degraded"}</StatusPill></div><p className="mt-2 text-xs text-kfl-muted">Scheduler: {data?.health?.scheduler}</p></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Database</div><Database className="text-kfl-blue" size={20} /></div><div className="mt-3"><StatusPill ok={dbOk}>{dbOk ? "Healthy" : "Degraded"}</StatusPill></div><p className="mt-2 text-xs text-kfl-muted">Integrity: {data?.database?.integrity}</p></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Active users</div><Users className="text-kfl-blue" size={20} /></div><div className="mt-3 text-3xl font-bold text-kfl-text">{data?.users?.active ?? 0}</div><p className="mt-2 text-xs text-kfl-muted">{data?.users?.total ?? 0} total profiles</p></div>
        <div className="app-surface p-5"><div className="flex items-center justify-between"><div className="app-label">Audit activity</div><ShieldCheck className="text-amber-600" size={20} /></div><div className="mt-3 text-3xl font-bold text-kfl-text">{data?.audit?.events_last_24h ?? 0}</div><p className="mt-2 text-xs text-kfl-muted">events in last 24 hours</p></div>
      </section>

      <section className="mb-6 grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Workflow posture</h2><p className="mt-1 text-xs text-kfl-muted">Current state counts; unexpected states are visible immediately.</p></div>
          <div className="grid grid-cols-2 gap-3 p-5 md:grid-cols-4">
            {Object.entries(workflowCounts).map(([state, count]) => <div key={state} className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-3"><div className="text-xs text-kfl-muted">{state.replace(/_/g, " ")}</div><div className="mt-1 text-2xl font-bold text-kfl-text">{String(count)}</div></div>)}
          </div>
        </div>
        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Table volumes</h2><p className="mt-1 text-xs text-kfl-muted">Persisted records across the core control domains.</p></div>
          <div className="grid grid-cols-2 gap-3 p-5 md:grid-cols-4">
            {Object.entries(data?.tables || {}).map(([table, count]) => <div key={table} className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-3"><div className="truncate text-xs text-kfl-muted">{table.replace(/_/g, " ")}</div><div className="mt-1 text-2xl font-bold text-kfl-text">{String(count)}</div></div>)}
          </div>
        </div>
      </section>

      <section className="app-surface mb-6 overflow-hidden">
        <div className="flex items-center gap-2 border-b border-kfl-border px-5 py-4">
          <Mail className="text-kfl-blue" size={18} />
          <div>
            <h2 className="font-bold text-kfl-text">Bulk user invitations</h2>
            <p className="mt-1 text-xs text-kfl-muted">Issue one-time invite codes so users can set their own passwords.</p>
          </div>
        </div>
        {inviteError && <div role="alert" className="m-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{inviteError}</div>}
        {inviteNotice && <div role="status" className="m-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{inviteNotice}</div>}
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
              <tr>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Username</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Assigned roles</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Invite code</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Setup URL</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-kfl-border">
              {(data?.user_profiles || []).map((user: any) => {
                const assignedRoles = user.roles || [user.role];
                const selectedRoles = roleDrafts[user.user_id] ?? assignedRoles;
                const existingInvite = issuedInvites.find((inv) => inv.user_id === user.user_id);
                return (
                  <tr key={user.user_id}>
                    <td className="px-5 py-3">
                      <div className="text-sm font-semibold text-kfl-text">{user.full_name}</div>
                      <div className="text-xs text-kfl-muted">{user.user_id} · {user.email}</div>
                    </td>
                    <td className="px-5 py-3 text-xs text-kfl-text">
                      {user.merged_into_user_id ? (
                        <>
                          <div className="font-mono">{assignedRoles.join(", ")}</div>
                          <div className="mt-1 text-[10px] text-kfl-muted">Merged into {user.merged_into_user_id}; historical ID retained</div>
                        </>
                      ) : user.is_active ? (
                        <div className="min-w-[230px] space-y-2">
                          <label htmlFor={`roles-${user.user_id}`} className="block font-semibold">Assigned roles for {user.full_name}</label>
                          <p className="text-[10px] text-kfl-muted">Use Ctrl/Command to select multiple roles.</p>
                          <select
                            id={`roles-${user.user_id}`}
                            name={`roles-${user.user_id}`}
                            aria-label={`Assigned roles for ${user.full_name}`}
                            multiple
                            size={Math.min(5, Math.max(3, data?.role_matrix?.length || 3))}
                            value={selectedRoles}
                            onChange={(event) => {
                              const roles = Array.from(event.currentTarget.selectedOptions, (option) => option.value).sort();
                              setRoleDrafts((current) => ({ ...current, [user.user_id]: roles }));
                            }}
                            className="w-full rounded border border-kfl-border bg-white px-2 py-1.5 text-xs text-kfl-text"
                          >
                            {(data?.role_matrix || []).map((profile: any) => <option key={profile.role} value={profile.role}>{profile.role.replace(/_/g, " ")}</option>)}
                          </select>
                          <div className="text-[10px] text-kfl-muted">Default role: {user.role}</div>
                          <button
                            type="button"
                            className="app-btn-secondary px-3 py-1.5 text-xs"
                            disabled={savingUserId !== null}
                            aria-label={`Save roles for ${user.full_name}`}
                            onClick={() => void saveRoles(user)}
                          >
                            {savingUserId === user.user_id ? "Saving…" : "Save roles"}
                          </button>
                        </div>
                      ) : (
                        <span className="font-mono">{assignedRoles.join(", ")}</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-xs text-kfl-text">
                      {!user.has_password && user.is_active ? (
                        <div className="space-y-2">
                          <label htmlFor={`invite-email-${user.user_id}`} className="block font-semibold">Email for invite</label>
                          <input
                            id={`invite-email-${user.user_id}`}
                            type="email"
                            value={inviteUsername === user.user_id ? inviteUsername : user.email || user.username}
                            onChange={(event) => {
                              setInviteUsername(user.user_id);
                              setInviteUsername(event.target.value);
                            }}
                            className="w-full rounded border border-kfl-border bg-white px-2 py-1 text-xs text-kfl-text"
                          />
                          <div className="text-[10px] text-kfl-muted">Roles: {assignedRoles.map((r: string) => r.replace(/_/g, " ")).join(", ")}</div>
                          <button
                            type="button"
                            className="app-btn-secondary px-3 py-1.5 text-xs"
                            disabled={invitingUserId === user.user_id || !inviteUsername.trim()}
                            onClick={() => void handleInvite()}
                          >
                            {invitingUserId === user.user_id ? "Sending…" : "Issue invite"}
                          </button>
                        </div>
                      ) : (
                        <span className="font-mono">{user.has_password ? "Password set" : "Inactive"}</span>
                      )}
                      {existingInvite && (
                        <div className="mt-2">
                          <span className="font-mono text-xs text-kfl-text">{existingInvite.invite_code}</span>
                          <div className="text-[10px] text-kfl-muted truncate" title={existingInvite.setup_url}>{existingInvite.setup_url}</div>
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 text-sm text-kfl-secondary">{user.department || "—"}</td>
                    <td className="px-5 py-3"><StatusPill ok={Boolean(user.is_active)}>{user.is_active ? "Active" : "Inactive"}</StatusPill></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Role matrix</h2><p className="mt-1 text-xs text-kfl-muted">Explicit permissions granted to each profile.</p></div>
        <div className="overflow-x-auto"><table className="min-w-full"><thead className="border-b border-kfl-border bg-kfl-surface-subtle"><tr><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Role</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Access level</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Permissions</th></tr></thead><tbody className="divide-y divide-kfl-border">{data?.role_matrix?.map((profile: any) => <tr key={profile.role}><td className="px-5 py-3 font-mono text-xs font-semibold text-kfl-text">{profile.role}</td><td className="px-5 py-3 text-sm text-kfl-secondary">{profile.access_level}</td><td className="px-5 py-3 text-xs text-kfl-secondary">{profile.permissions.join(", ")}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
