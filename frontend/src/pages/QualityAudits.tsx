import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { ClipboardCheck, Wrench } from "lucide-react";

function auditStatusClass(status: string) {
  switch (status) {
    case "completed": return "app-status app-status-healthy";
    case "in_progress": return "app-status app-status-info";
    case "planned": return "app-status app-status-info";
    case "cancelled": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}

function carStatusClass(status: string) {
  switch (status) {
    case "closed": return "app-status app-status-healthy";
    case "verified": return "app-status app-status-healthy";
    case "open": return "app-status app-status-info";
    case "in_progress": return "app-status app-status-info";
    case "overdue": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}

export function QualityAudits() {
  const qc = useQueryClient();
  const { data: audits = [], isLoading } = useQuery({
    queryKey: ["quality-audits"],
    queryFn: () => api.get("/p1/quality-audits").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/quality-audits", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quality-audits"] });
      setShowForm(false);
      setTitle("");
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Quality Management</div>
          <h1 className="app-title">Quality Audits</h1>
          <p className="app-subtitle">Plan, execute, and track quality audits and findings.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <ClipboardCheck size={16} /> {showForm ? "Cancel" : "New Audit"}
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Audits</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{audits.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Completed</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{audits.filter((a: any) => a.status === "completed").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">In Progress</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{audits.filter((a: any) => a.status === "in_progress").length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <input value={showForm ? title : ""} onChange={(e) => setTitle(e.target.value)} placeholder="Search audits…" className="app-input pl-9 relative z-10" />
          </div>
          <select className="app-input w-full md:w-auto">
            <option value="">All statuses</option>
            <option value="planned">Planned</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
          </select>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New Quality Audit</div>
                <p className="text-xs text-kfl-muted">Schedule a quality audit.</p>
              </div>
              <button onClick={() => setShowForm(false)} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            <input className="app-input mb-3" placeholder="Audit title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <button
              disabled={!title.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate({ title, auditor_id: "u-quality" })}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Creating…" : "Create Audit"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading audits…</div>
        ) : audits.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <ClipboardCheck size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No quality audits.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create your first audit to begin quality tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Findings</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {audits.map((a: any) => (
                  <tr key={a.audit_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{a.audit_id}</td>
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{a.title}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.audit_type}</td>
                    <td className="px-4 py-4">
                      <span className={auditStatusClass(a.status)}>{a.status}</span>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.findings_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export function CorrectiveActions() {
  const { data: cars = [], isLoading } = useQuery({
    queryKey: ["corrective-actions"],
    queryFn: () => api.get("/p1/corrective-actions").then((r: any) => r.data),
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Quality Management</div>
          <h1 className="app-title">Corrective Action Requests</h1>
          <p className="app-subtitle">Track corrective actions from audit findings through to closure.</p>
        </div>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total CARs</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{cars.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{cars.filter((c: any) => c.status === "open").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Closed / Verified</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{cars.filter((c: any) => c.status === "closed" || c.status === "verified").length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="overflow-x-auto">
          {isLoading && (
            <div className="p-10 text-center text-sm text-kfl-muted">Loading CARs…</div>
          )}
          {!isLoading && cars.length === 0 && (
            <div className="app-surface border-dashed p-10 text-center">
              <Wrench size={26} className="mx-auto mb-2 text-kfl-muted" />
              <p className="text-sm font-bold text-kfl-text">No corrective actions.</p>
              <p className="mt-1 text-xs text-kfl-muted">Create CARs from audit findings to track remediation.</p>
            </div>
          )}
          {!isLoading && cars.length > 0 && (
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Owner</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Due Date</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {cars.map((c: any) => (
                  <tr key={c.car_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{c.car_id}</td>
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{c.title}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{c.owner_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{c.due_date || "—"}</td>
                    <td className="px-4 py-4">
                      <span className={carStatusClass(c.status)}>{c.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}