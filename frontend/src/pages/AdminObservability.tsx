import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Activity, Database, GitBranch, RefreshCw, ShieldCheck, Users } from "lucide-react";
import api from "../api/client";

function StatusPill({ ok, children }: { ok: boolean; children: ReactNode }) {
  return <span className={`app-status ${ok ? "app-status-healthy" : "app-status-critical"}`}>{children}</span>;
}

export default function AdminObservability() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["admin-observability"],
    queryFn: () => api.get("/p0/admin/observability").then((response: any) => response.data),
    refetchInterval: 30000,
  });

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
          <p className="app-subtitle">Read-only control-plane telemetry for system health, workflow posture, audit activity, and access profiles.</p>
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
        <div className="flex items-center gap-2 border-b border-kfl-border px-5 py-4"><GitBranch className="text-kfl-blue" size={18} /><div><h2 className="font-bold text-kfl-text">User profiles and effective access</h2><p className="mt-1 text-xs text-kfl-muted">The role matrix is the enforcement source used by the API.</p></div></div>
        <div className="overflow-x-auto"><table className="min-w-full"><thead className="border-b border-kfl-border bg-kfl-surface-subtle"><tr><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">User</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Profile</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Department</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Status</th></tr></thead><tbody className="divide-y divide-kfl-border">{(data?.user_profiles || []).map((user: any) => <tr key={user.user_id}><td className="px-5 py-3"><div className="text-sm font-semibold text-kfl-text">{user.full_name}</div><div className="text-xs text-kfl-muted">{user.user_id} · {user.email}</div></td><td className="px-5 py-3 font-mono text-xs text-kfl-text">{user.role}</td><td className="px-5 py-3 text-sm text-kfl-secondary">{user.department || "—"}</td><td className="px-5 py-3"><StatusPill ok={Boolean(user.is_active)}>{user.is_active ? "Active" : "Inactive"}</StatusPill></td></tr>)}</tbody></table></div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Role matrix</h2><p className="mt-1 text-xs text-kfl-muted">Explicit permissions granted to each profile.</p></div>
        <div className="overflow-x-auto"><table className="min-w-full"><thead className="border-b border-kfl-border bg-kfl-surface-subtle"><tr><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Role</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Access level</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Permissions</th></tr></thead><tbody className="divide-y divide-kfl-border">{(data?.role_matrix || []).map((profile: any) => <tr key={profile.role}><td className="px-5 py-3 font-mono text-xs font-semibold text-kfl-text">{profile.role}</td><td className="px-5 py-3 text-sm text-kfl-secondary">{profile.access_level}</td><td className="px-5 py-3 text-xs text-kfl-secondary">{profile.permissions.join(", ")}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
