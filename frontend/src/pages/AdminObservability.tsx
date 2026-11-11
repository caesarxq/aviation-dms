import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  Database,
  History,
  Play,
  RefreshCw,
  ShieldCheck,
  Users,
  Wifi,
} from "lucide-react";
import api from "../api/client";

function StatusPill({ ok, children, size }: { ok?: boolean; children: ReactNode; size?: "sm" | "md" | "xs" }) {
  const base = "app-status px-2 py-0.5 rounded font-semibold";
  const sizeClass = size === "xs" ? "text-[9px] px-1" : size === "sm" ? "text-[10px] px-1.5" : "text-xs px-2";
  return <span className={`${base} ${ok ? "app-status-healthy" : "app-status-critical"} ${sizeClass}`}>{children}</span>;
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

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["admin-observability"],
    queryFn: () => api.get("/p0/admin/observability").then((response: any) => response.data),
    refetchInterval: 15000,
  });

  // Backup trigger mutation
  const backupRunMutation = useMutation({
    mutationFn: () => api.post("/p0/backup/run").then((r: any) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
      queryClient.invalidateQueries({ queryKey: ["backup-history"] });
      setBackupNotice("Backup run triggered successfully.");
    },
    onError: (cause: any) => {
      setBackupError(cause?.response?.data?.detail || "Backup run failed.");
    },
  });

  // Scanner test mutation
  const scannerTestMutation = useMutation({
    mutationFn: () => api.post("/p0/scanner/test").then((r: any) => r.data),
    onSuccess: (result) => {
      setScannerTestResult(result);
      queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
    },
    onError: (cause: any) => {
      setScannerTestResult({ configured: false, reachable: null, detail: cause?.response?.data?.detail || "Scanner test failed" });
    },
  });

  // Backup history query
  const { data: backupHistory } = useQuery({
    queryKey: ["backup-history"],
    queryFn: () => api.get("/p0/backup/history?limit=10").then((response: any) => response.data),
    refetchInterval: 30000,
    enabled: true,
  });

  const [backupNotice, setBackupNotice] = useState("");
  const [backupError, setBackupError] = useState("");
  const [scannerTestResult, setScannerTestResult] = useState<any>(null);

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
  const health = data?.health || {};
  const backup = health.backup || {};
  const scanner = health.scanner || {};

  const backupRuns = backupHistory?.events || [];

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Administration</div>
          <h1 className="app-title">System Observability</h1>
          <p className="app-subtitle">System health, workflow posture, audit activity, backup state, and administrator-controlled access profiles.</p>
        </div>
        <button className="app-btn-secondary" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} /> Refresh
        </button>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">API health</div>
            <Activity className="text-emerald-600" size={20} />
          </div>
          <div className="mt-3"><StatusPill ok={healthOk}>{healthOk ? "Healthy" : "Degraded"}</StatusPill></div>
          <p className="mt-2 text-xs text-kfl-muted">Scheduler: {data?.health?.scheduler}</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Database</div>
            <Database className="text-kfl-blue" size={20} />
          </div>
          <div className="mt-3"><StatusPill ok={dbOk}>{dbOk ? "Healthy" : "Degraded"}</StatusPill></div>
          <p className="mt-2 text-xs text-kfl-muted">Integrity: {data?.database?.integrity}</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Active users</div>
            <Users className="text-kfl-blue" size={20} />
          </div>
          <div className="mt-3 text-3xl font-bold text-kfl-text">{data?.users?.active ?? 0}</div>
          <p className="mt-2 text-xs text-kfl-muted">{data?.users?.total ?? 0} total profiles</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Audit activity</div>
            <ShieldCheck className="text-amber-600" size={20} />
          </div>
          <div className="mt-3 text-3xl font-bold text-kfl-text">{data?.audit?.events_last_24h ?? 0}</div>
          <p className="mt-2 text-xs text-kfl-muted">events in last 24 hours</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Backup scheduler</div>
            <Play className={backup.enabled ? "text-emerald-600" : "text-kfl-muted"} size={20} />
          </div>
          <div className="mt-3"><StatusPill ok={backup.enabled && backup.running}>{backup.running ? "Running" : backup.enabled ? "Stopped" : "Disabled"}</StatusPill></div>
          <p className="mt-2 text-xs text-kfl-muted">{backup.enabled ? `Runs: ${backup.run_count} · Failures: ${backup.failure_count}` : "Backups not configured"}</p>
          {backup.last_error && (
            <p className="mt-1 text-xs text-rose-600" title={backup.last_error}>Last error: {backup.last_error.slice(0, 60)}…</p>
          )}
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">ClamAV scanner</div>
            <Wifi className={scanner.reachable === true ? "text-emerald-600" : scanner.reachable === false ? "text-rose-600" : "text-kfl-muted"} size={20} />
          </div>
          <div className="mt-3">
            {scanner.configured === false ? (
              <StatusPill ok={false}>Not configured</StatusPill>
            ) : scanner.reachable === true ? (
              <StatusPill ok={true}>Reachable</StatusPill>
            ) : scanner.reachable === false ? (
              <StatusPill ok={false}>Unreachable</StatusPill>
            ) : (
              <span className="text-xs text-kfl-muted">Testing…</span>
            )}
          </div>
          <p className="mt-2 text-xs text-kfl-muted">{scanner.detail || (scanner.configured === false ? "Set DMS_CLAMD_HOST/PORT" : "")}</p>
          <button
            className="mt-2 app-btn-secondary px-3 py-1.5 text-xs"
            onClick={() => scannerTestMutation.mutate()}
            disabled={scannerTestMutation.isPending}
          >
            {scannerTestMutation.isPending ? "Testing…" : "Test connection"}
          </button>
          {scannerTestResult && (
            <p className="mt-1 text-xs">{scannerTestResult.reachable === true ? "✓ Reachable" : scannerTestResult.reachable === false ? "✗ Unreachable" : "—"} {scannerTestResult.detail}</p>
          )}
        </div>
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

      <section className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="app-surface overflow-hidden">
          <div className="flex items-center gap-2 border-b border-kfl-border px-5 py-4">
            <History className="text-kfl-blue" size={18} />
            <div>
              <h2 className="font-bold text-kfl-text">Backup control</h2>
              <p className="mt-1 text-xs text-kfl-muted">Trigger an on-demand backup and review recent backup history.</p>
            </div>
          </div>
          <div className="p-5">
            <button
              className="app-btn-primary px-4 py-2 text-sm"
              onClick={() => backupRunMutation.mutate()}
              disabled={backupRunMutation.isPending || !backup.enabled}
            >
              {backupRunMutation.isPending ? "Running backup…" : "Run backup now"}
            </button>
            {!backup.enabled && (
              <p className="mt-3 text-xs text-rose-600">Backup scheduler is not enabled. Set DMS_BACKUP_ENABLED=true and configure DMS_BACKUP_DATA_ROOT and DMS_BACKUP_DEST_ROOT.</p>
            )}
            {backupNotice && <div role="status" className="mt-3 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{backupNotice}</div>}
            {backupError && <div role="alert" className="mt-3 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{backupError}</div>}
          </div>
          <div className="border-t border-kfl-border px-5 py-4">
            <h3 className="font-semibold text-kfl-text text-sm">Recent backup history</h3>
            <div className="overflow-x-auto mt-3">
              <table className="min-w-full text-xs">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Time</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Action</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Status</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {backupRuns.length === 0 ? (
                    <tr><td colSpan={4} className="px-3 py-4 text-center text-xs text-kfl-muted">No backup events recorded yet.</td></tr>
                  ) : (
                    backupRuns.slice(0, 10).map((event: any) => {
                      const details = typeof event.details === "string" ? event.details : JSON.stringify(event.details || {});
                      const accepted = event.details?.accepted;
                      return (
                        <tr key={event.event_id}>
                          <td className="px-3 py-2 font-mono">{event.timestamp?.slice(0, 19).replace("T", " ") ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{event.action}</td>
                          <td className="px-3 py-2">
                            <StatusPill ok={accepted !== false} size="xs">{accepted === true ? "Accepted" : accepted === false ? "Rejected" : event.action}</StatusPill>
                          </td>
                          <td className="px-3 py-2 truncate max-w-[200px] text-kfl-muted">{details.slice(0, 100)}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Scanner status</h2><p className="mt-1 text-xs text-kfl-muted">Malware scanner (clamd) connectivity and last probe result.</p></div>
          <div className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="font-bold text-kfl-text">ClamAV endpoint</div>
                <div className="text-xs text-kfl-muted font-mono">{scanner.host ?? "—"}:{scanner.port ?? "—"}</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold">
                  {scanner.reachable === true ? "OK" : scanner.reachable === false ? "DOWN" : "—"}
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded border border-kfl-border bg-kfl-surface">
                <span className="text-sm text-kfl-muted">Configured</span>
                <span className="text-sm font-mono">{scanner.configured === true ? "Yes" : "No"}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded border border-kfl-border bg-kfl-surface">
                <span className="text-sm text-kfl-muted">Reachable</span>
                <span className={`text-sm font-mono ${scanner.reachable === true ? "text-emerald-600" : scanner.reachable === false ? "text-rose-600" : "text-kfl-muted"}`}>
                  {scanner.reachable === true ? "Yes" : scanner.reachable === false ? "No" : "Unknown"}
                </span>
              </div>
            </div>
            <p className="mt-3 text-xs text-kfl-muted">{scanner.detail || "No scanner configured. Set DMS_CLAMD_HOST and DMS_CLAMD_PORT."}</p>
          </div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Bulk user invitations</h2><p className="mt-1 text-xs text-kfl-muted">Issue one-time invite codes so users can set their own passwords.</p></div>
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
                const controlKey = encodeURIComponent(user.user_id).replace(/%/g, "_");
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
                          <label htmlFor={`roles-${controlKey}`} className="block font-semibold">Assigned roles for {user.full_name}</label>
                          <p className="text-[10px] text-kfl-muted">Use Ctrl/Command to select multiple roles.</p>
                          <select
                            id={`roles-${controlKey}`}
                            name={`roles-${controlKey}`}
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
                          <label htmlFor={`invite-email-${controlKey}`} className="block font-semibold">Email for invite</label>
                          <input
                            id={`invite-email-${controlKey}`}
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
