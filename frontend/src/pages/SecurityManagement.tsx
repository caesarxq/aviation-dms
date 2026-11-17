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
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

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
        {canManage && <Button
          onClick={() => setShowForm(!showForm)}
          variant="default"
          size="sm"
        >
          <AlertTriangle size={16} /> {showForm ? "Cancel" : "Report Incident"}
        </Button>}
        {hasPermission("safety:create") && <Button
          onClick={() => setShowSecurityReviewModal(true)}
          variant="outline"
          size="sm"
        >
          <Calendar size={16} /> Schedule Review
        </Button>}
        {hasPermission("safety:create") && <Button
          onClick={() => setShowOutsourcedModal(true)}
          variant="outline"
          size="sm"
        >
          <Users size={16} /> Register Outsourced Function
        </Button>}
      </header>

      {canReadSensitive && summaryError && <div role="alert" className="mb-4 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">Unable to load security incident metrics. <Button variant="outline" size="sm" type="button" onClick={() => void refetchSummary()}>
        Retry
      </Button>
      </div>}
      {canReadSensitive && <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Incidents</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{summaryLoading ? "…" : summaryError ? "—" : incidentSummary?.total ?? "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Critical / High</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-danger">{summaryLoading ? "…" : summaryError ? "—" : incidentSummary?.critical_high ?? "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-warning">{summaryLoading ? "…" : summaryError ? "—" : incidentSummary?.open ?? "—"}</div>
        </div>
      </section>}

      <section className="app-surface overflow-hidden">
        {canReadSensitive && <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <ShieldAlert size={16} className="pointer-events-none absolute left-3 top-3 text-kfl-muted" />
            <Input id="search_incidents_85" name="search_incidents" type="search" aria-label="Search security incidents" value={search} onChange={(e) => { setPage(0); setSearch(e.target.value); }} placeholder="Search incidents…" className="pl-9 relative z-10" />
          </div>
          <select id="select_field_92" name="status" aria-label="Filter security incidents by status" value={statusFilter} onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }} className="w-full md:w-auto">
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
              <Button variant="outline" size="sm" onClick={() => { setShowForm(false); setDirty(false); }}>
                Cancel
              </Button>
            </div>
            <FormField htmlFor="incident_title_109" label="Incident title" hint="Summarize the security event without including sensitive credentials or secrets." required>
              <Input id="incident_title_109" name="incident_title" aria-describedby="incident_title_109-error" aria-invalid={!!smFieldErrors.title} className={smFieldErrors.title ? "border-rose-400" : ""} placeholder="Security incident title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {smFieldErrors.title && <p id="incident_title_109-error" className="text-[11px] text-rose-700 mt-1">{smFieldErrors.title}</p>}
            </FormField>
            <Button
              disabled={!smIsValid || createMutation.isPending}
              onClick={() => createMutation.mutate({ title, description: "Security incident", incident_type: "unauthorized_access" })}
              variant="default"
              size="sm"
              className="w-full disabled:opacity-60"
            >
              {createMutation.isPending ? "Submitting…" : "Report Incident"}
            </Button>
            {createMutation.isError && <p role="alert" className="mt-3 text-sm text-kfl-status-danger">Unable to report security incident. {createMutation.error instanceof Error ? createMutation.error.message : "Please try again."}</p>}
          </div>
        ) : null}

        {canReadSensitive && isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading incidents…</div>
        ) : canReadSensitive && isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="text-sm font-semibold text-kfl-status-danger">Unable to load security incidents.</p>
            <Button variant="outline" size="sm" type="button" onClick={() => void refetch()}>
              Retry
            </Button>
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
            {page > 0 && <Button variant="outline" size="sm" type="button" disabled={isLoading} onClick={() => setPage((current) => current - 1)}>
              Previous page
            </Button>}
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
                    <td className="px-4 py-4"><Badge variant={i.severity === "critical" || i.severity === "high" ? "destructive" : i.severity === "medium" ? "secondary" : "default"} className={`badge ${i.severity === "critical" || i.severity === "high" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : i.severity === "medium" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{i.severity}</Badge></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-kfl-border p-4">
            <span className="text-sm text-kfl-muted">Page {page + 1}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" type="button" disabled={page === 0 || isLoading} onClick={() => setPage((current) => current - 1)}>
                Previous page
              </Button>
              <Button variant="outline" size="sm" type="button" disabled={incidents.length < pageSize || isLoading} onClick={() => setPage((current) => current + 1)}>
                Next page
              </Button>
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
