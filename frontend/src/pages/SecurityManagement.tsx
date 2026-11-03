import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { ShieldAlert, AlertTriangle, Calendar, Users } from "lucide-react";
import FormField from "../components/ui/FormField";
import { SecurityReviewsModal } from "../components/ui/modals/SecurityReviewsModal";
import { OutsourcedFunctionsModal } from "../components/ui/modals/OutsourcedFunctionsModal";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";

function incidentSeverityClass(severity: string) {
  switch (severity) {
    case "critical": return "app-status app-status-critical";
    case "high": return "app-status app-status-warning";
    case "medium": return "app-status app-status-info";
    case "low": return "app-status app-status-healthy";
    default: return "app-status app-status-info";
  }
}

export function SecurityManagement() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const canReadSensitive = hasPermission("security:read_sensitive");
  const canManage = hasPermission("security:manage");
  const [showForm, setShowForm] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [title, setTitle] = useState("");
  const [showSecurityReviewModal, setShowSecurityReviewModal] = useState(false);
  const [showOutsourcedModal, setShowOutsourcedModal] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 50;
  const trimmedSearch = canReadSensitive ? search.trim() : "";
  const requestedStatus = canReadSensitive ? statusFilter : "";
  const { data: incidents = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["security-incidents", trimmedSearch, requestedStatus, page],
    queryFn: () => api.get("/p1/security-incidents", {
      params: {
        ...(trimmedSearch ? { search: trimmedSearch } : {}),
        ...(requestedStatus ? { status: requestedStatus } : {}),
        limit: pageSize,
        offset: page * pageSize,
      },
    }).then((r: any) => r.data),
    enabled: canReadSensitive,
  });
  const { data: incidentSummary, isLoading: summaryLoading, isError: summaryError, refetch: refetchSummary } = useQuery({
    queryKey: ["security-incident-summary"],
    queryFn: () => api.get("/p1/security-incidents/summary").then((r: any) => r.data),
    enabled: canReadSensitive,
  });

  const { errors: smFieldErrors, isValid: smIsValid } = useValidation(
    { title },
    {
      title: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  useEffect(() => {
    if (!canManage) {
      setShowForm(false);
      setDirty(false);
      setTitle("");
    }
  }, [canManage]);

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/security-incidents", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-incidents"] });
      qc.invalidateQueries({ queryKey: ["security-incident-summary"] });
      setShowForm(false);
      setDirty(false);
      setTitle("");
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Security Management</div>
          <h1 className="app-title">Security Incidents</h1>
          <p className="app-subtitle">Report, track, and manage security incidents and assessments.</p>
        </div>
        {canManage && <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <AlertTriangle size={16} /> {showForm ? "Cancel" : "Report Incident"}
        </button>}
        {hasPermission("safety:create") && <button
          onClick={() => setShowSecurityReviewModal(true)}
          className="app-btn-secondary"
        >
          <Calendar size={16} /> Schedule Review
        </button>}
        {hasPermission("safety:create") && <button
          onClick={() => setShowOutsourcedModal(true)}
          className="app-btn-secondary"
        >
          <Users size={16} /> Register Outsourced Function
        </button>}
      </header>

      {canReadSensitive && summaryError && <div role="alert" className="mb-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">Unable to load security incident metrics. <button type="button" className="font-semibold underline" onClick={() => void refetchSummary()}>Retry</button></div>}
      {canReadSensitive && <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Incidents</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{summaryLoading ? "…" : summaryError ? "—" : incidentSummary?.total ?? "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Critical / High</div>
          <div className="mt-2 text-2xl font-bold text-red-700">{summaryLoading ? "…" : summaryError ? "—" : incidentSummary?.critical_high ?? "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{summaryLoading ? "…" : summaryError ? "—" : incidentSummary?.open ?? "—"}</div>
        </div>
      </section>}

      <section className="app-surface overflow-hidden">
        {canReadSensitive && <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <ShieldAlert size={16} className="pointer-events-none absolute left-3 top-3 text-kfl-muted" />
            <input id="search_incidents_85" name="search_incidents"
              value={search}
              type="search"
              aria-label="Search security incidents"
              onChange={(e) => { setPage(0); setSearch(e.target.value); }}
              placeholder="Search incidents…"
              className="app-input pl-9 relative z-10"
            />
          </div>
          <select id="select_field_92" name="status" aria-label="Filter security incidents by status" value={statusFilter} onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }} className="app-input w-full md:w-auto">
            <option value="">All statuses</option>
            <option value="reported">Reported</option>
            <option value="investigating">Investigating</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>}

        {!canReadSensitive ? (
          <div role="alert" className="p-10 text-center text-sm text-kfl-secondary">
            Security incident details are restricted to users with security:read_sensitive access.
          </div>
        ) : showForm && canManage ? (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New Security Incident</div>
                <p className="text-xs text-kfl-muted">Report a security incident for investigation.</p>
              </div>
              <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            <FormField htmlFor="incident_title_109" label="Incident title" hint="Summarize the security event without including sensitive credentials or secrets." required>
              <input id="incident_title_109" name="incident_title" aria-describedby="incident_title_109-error" aria-invalid={!!smFieldErrors.title} className={`app-input ${smFieldErrors.title ? "border-rose-400" : ""}`} placeholder="Security incident title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {smFieldErrors.title && <p id="incident_title_109-error" className="text-[11px] text-rose-700 mt-1">{smFieldErrors.title}</p>}
            </FormField>
            <button
              disabled={!smIsValid || createMutation.isPending}
              onClick={() => createMutation.mutate({ title, description: "Security incident", incident_type: "unauthorized_access" })}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Submitting…" : "Report Incident"}
            </button>
            {createMutation.isError && <p role="alert" className="mt-3 text-sm text-rose-800">Unable to report security incident. {createMutation.error instanceof Error ? createMutation.error.message : "Please try again."}</p>}
          </div>
        ) : null}

        {canReadSensitive && isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading incidents…</div>
        ) : canReadSensitive && isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="text-sm font-semibold text-rose-800">Unable to load security incidents.</p>
            <button type="button" onClick={() => void refetch()} className="app-btn-secondary mt-3">Retry</button>
          </div>
        ) : canReadSensitive && incidents.length === 0 && page === 0 && !trimmedSearch && !requestedStatus ? (
          <div className="app-surface border-dashed p-10 text-center">
            <ShieldAlert size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No security incidents.</p>
            <p className="mt-1 text-xs text-kfl-muted">Report your first incident to begin security tracking.</p>
          </div>
        ) : canReadSensitive && incidents.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">
            <p>{page > 0 ? "No incidents on this page." : "No incidents match these filters."}</p>
            {page > 0 && <button type="button" className="app-btn-secondary mt-3" disabled={isLoading} onClick={() => setPage((current) => current - 1)}>Previous page</button>}
          </div>
        ) : canReadSensitive ? (
          <>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Severity</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {incidents.map((i: any) => (
                  <tr key={i.incident_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{i.incident_id}</td>
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{i.title}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.incident_type}</td>
                    <td className="px-4 py-4">
                      <span className={incidentSeverityClass(i.severity)}>{i.severity}</span>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-kfl-border p-4">
            <span className="text-sm text-kfl-muted">Page {page + 1}</span>
            <div className="flex gap-2">
              <button type="button" className="app-btn-secondary" disabled={page === 0 || isLoading} onClick={() => setPage((current) => current - 1)}>Previous page</button>
              <button type="button" className="app-btn-secondary" disabled={incidents.length < pageSize || isLoading} onClick={() => setPage((current) => current + 1)}>Next page</button>
            </div>
          </div>
          </>
        ) : null}
      </section>
      <SecurityReviewsModal open={showSecurityReviewModal} onClose={() => setShowSecurityReviewModal(false)} />
      <OutsourcedFunctionsModal open={showOutsourcedModal} onClose={() => setShowOutsourcedModal(false)} />
    </div>
  );
}
