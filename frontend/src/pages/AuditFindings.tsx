import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { auditApi } from "../api/audit";
import type { AuditFinding, AuditFindingStatus, AuditReport } from "../api/audit";
import { AlertTriangle, Plus, RefreshCw } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useAuth } from "../auth/AuthContext";

function levelClass(level: number | undefined) {
  switch (level) {
    case 3:
      return "app-status app-status-critical";
    case 2:
      return "app-status app-status-warning";
    case 1:
      return "app-status app-status-info";
    default:
      return "app-status app-status-info";
  }
}

function statusClass(status: string) {
  switch (status) {
    case "open":
      return "app-status app-status-warning";
    case "in_progress":
      return "app-status app-status-info";
    case "verified":
      return "app-status app-status-healthy";
    case "closed":
      return "app-status app-status-healthy";
    default:
      return "app-status app-status-info";
  }
}

export function AuditFindings() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { findingId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = useAuth();
  const auditFilter = searchParams.get("audit_id") ?? "";
  const pageSize = 50;
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<AuditFindingStatus | "">("");
  const { data: findings = [], isLoading, isError, refetch } = useQuery<AuditFinding[]>({
    queryKey: ["audit-findings", auditFilter, search, statusFilter, page],
    queryFn: () => auditApi.listAuditFindings({
      ...(auditFilter ? { audit_id: auditFilter } : {}),
      ...(search.trim() ? { search: search.trim() } : {}),
      ...(statusFilter ? { status: statusFilter } : {}),
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: !findingId,
  });
  const { data: detailFinding, isLoading: detailLoading, isError: detailError } = useQuery<AuditFinding>({
    queryKey: ["audit-finding", findingId],
    queryFn: () => auditApi.getAuditFinding(findingId!),
    enabled: !!findingId,
  });
  const { data: audits = [], isLoading: auditsLoading, isError: auditsError, refetch: refetchAudits } = useQuery<AuditReport[]>({
    queryKey: ["audit-reports"],
    queryFn: () => auditApi.listAuditReports(),
  });
  const [showForm, setShowForm] = useState(false);
  const [findingNumber, setFindingNumber] = useState("");
  const [area, setArea] = useState("");
  const [level, setLevel] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [auditId, setAuditId] = useState(auditFilter);
  const [mutationError, setMutationError] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => auditApi.createAuditFinding(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["audit-findings"] });
      setShowForm(false);
      setFindingNumber("");
      setArea("");
      setLevel("");
      setTitle("");
      setDescription("");
      setAuditId("");
      setMutationError("");
    },
    onError: () => setMutationError("Unable to create audit finding. Please check the details and try again."),
  });

  if (findingId) {
    return (
      <div className="app-page">
        <header className="app-page-header"><div><div className="app-eyebrow">Audit Management</div><h1 className="app-title">Audit Finding Details</h1></div></header>
        {detailError ? <div role="alert" className="app-surface p-5 text-rose-800">Unable to load audit finding details.</div> : detailLoading ? <div className="app-surface p-5">Loading finding…</div> : detailFinding ? (
          <section className="app-surface space-y-3 p-5">
            <h2 className="text-lg font-bold text-kfl-text">{detailFinding.finding_number}: {detailFinding.title}</h2>
            <p className="text-sm text-kfl-secondary">{detailFinding.description || "No description provided."}</p>
            <p className="text-sm text-kfl-secondary">Area: {detailFinding.area} · Level {detailFinding.level} · {detailFinding.status.replace(/_/g, " ")}</p>
            <Link className="text-sm font-semibold text-kfl-blue underline" to={`/audit-findings?audit_id=${encodeURIComponent(detailFinding.audit_id)}`}>Back to audit findings</Link>
          </section>
        ) : <div className="app-surface p-5">Audit finding not found.</div>}
      </div>
    );
  }

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Audit Management</div>
          <h1 className="app-title">Audit Findings</h1>
          <p className="app-subtitle">
            View and manage audit findings and link them to corrective actions.
          </p>
        </div>
        {hasPermission("audit_finding:create") && <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Finding"}
        </button>}
        <button
          onClick={() => qc.invalidateQueries({ queryKey: ["audit-findings"] })}
          className="app-btn-secondary"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </header>

      {showForm && (
        <div className="app-surface p-5 mb-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="app-label mb-1">New Audit Finding</div>
              <p className="text-xs text-kfl-muted">
                Record a new audit finding and link it to a corrective action.
              </p>
            </div>
            <button
              type="button"
              onClick={() => { setShowForm(false); setMutationError(""); }}
              className="app-btn-secondary px-4 py-2 text-sm"
            >
              Cancel
            </button>
          </div>
          {mutationError && <p role="alert" className="mb-3 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{mutationError}</p>}
          {auditsError && <div role="alert" className="mb-3 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">Unable to load audit engagements. <button type="button" className="font-semibold underline" onClick={() => void refetchAudits()}>Retry</button></div>}
          <div className="space-y-3 mb-4">
            <FormField htmlFor="audit_engagement" label="Audit engagement" required>
              <select id="audit_engagement" name="audit_id" aria-label="Audit engagement" className="app-input" value={auditId} onChange={(event) => setAuditId(event.target.value)} disabled={auditsLoading || auditsError}>
                <option value="">Select an audit</option>
                {audits.map((audit) => <option key={audit.audit_id} value={audit.audit_id}>{audit.audit_number} — {audit.audit_date}</option>)}
              </select>
            </FormField>
            <FormField
              htmlFor="finding_number"
              label="Finding Number"
              hint="e.g. 1, 2, 3…"
              required
            >
              <input
                id="finding_number"
                name="finding_number"
                className="app-input"
                placeholder="1"
                value={findingNumber}
                onChange={(e) => setFindingNumber(e.target.value)}
              />
            </FormField>
            <FormField
              htmlFor="area"
              label="Area"
              hint="e.g. Safety, Security, Safety & Security"
              required
            >
              <input
                id="area"
                name="area"
                className="app-input"
                placeholder="Safety"
                value={area}
                onChange={(e) => setArea(e.target.value)}
              />
            </FormField>
            <FormField htmlFor="level" label="Level" hint="2 or 3" required>
              <select
                id="level"
                name="level"
                className="app-input"
                value={level}
                onChange={(e) => setLevel(e.target.value)}
              >
                <option value="">Select level</option>
                <option value="2">Level 2</option>
                <option value="3">Level 3</option>
              </select>
            </FormField>
            <FormField htmlFor="title" label="Title" hint="Short title" required>
              <input
                id="title"
                name="title"
                className="app-input"
                placeholder="Finding title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </FormField>
            <FormField
              htmlFor="description"
              label="Description"
              hint="Detailed description of the finding"
              required
            >
              <textarea
                id="description"
                name="description"
                className="app-input"
                placeholder="Describe the finding"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </FormField>
          </div>
          <button
            type="button"
            disabled={
              createMutation.isPending || !auditId || auditsLoading || auditsError ||
              !findingNumber ||
              !area ||
              !level ||
              !title ||
              !description
            }
            onClick={() =>
              createMutation.mutate({
                finding_number: findingNumber,
                audit_id: auditId,
                area,
                level: parseInt(level, 10),
                title,
                description,
              })
            }
            className="app-btn-primary w-full disabled:opacity-60"
          >
            {createMutation.isPending ? "Creating…" : "Create Finding"}
          </button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <input type="search" id="audit-finding-search" name="search" aria-label="Search audit findings" className="app-input min-w-0 flex-1 md:max-w-md" value={search} onChange={(event) => { setPage(0); setSearch(event.target.value); }} placeholder="Search audit findings…" />
          <select id="audit-finding-audit-filter" name="audit_id" aria-label="Filter findings by audit" className="app-input w-full md:w-auto" value={auditFilter} onChange={(event) => { const next = new URLSearchParams(searchParams); if (event.target.value) next.set("audit_id", event.target.value); else next.delete("audit_id"); setPage(0); setSearchParams(next); }}>
            <option value="">All audits</option>
            {audits.map((audit) => <option key={audit.audit_id} value={audit.audit_id}>{audit.audit_number}</option>)}
          </select>
          <select id="audit-finding-status-filter" name="status" aria-label="Filter audit findings by status" className="app-input w-full md:w-auto" value={statusFilter} onChange={(event) => { setPage(0); setStatusFilter(event.target.value as AuditFindingStatus | ""); }}>
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In progress</option>
            <option value="closed">Closed</option>
          </select>
          <div className="text-sm font-semibold text-kfl-text">Findings on this page ({findings.length})</div>
        </div>

        {isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="text-sm font-semibold text-rose-800">Unable to load audit findings.</p>
            <button type="button" onClick={() => void refetch()} className="app-btn-secondary mt-3" aria-label="Retry loading audit findings">Retry</button>
          </div>
        ) : isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">
            Loading findings…
          </div>
        ) : findings.length === 0 && page === 0 && !search.trim() && !statusFilter && !auditFilter ? (
          <div className="app-surface border-dashed p-10 text-center">
            <AlertTriangle size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No audit findings recorded.</p>
            <p className="mt-1 text-xs text-kfl-muted">
              Create your first audit finding to begin tracking findings.
            </p>
          </div>
        ) : findings.length === 0 && page === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">No audit findings match these filters.</div>
        ) : findings.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">
            <p>No findings on this page.</p>
            <button type="button" className="app-btn-secondary mt-3" disabled={isLoading} onClick={() => setPage((current) => current - 1)}>Previous page</button>
          </div>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Finding #
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Area
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Level
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Title
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {findings.map((f: AuditFinding) => (
                  <tr key={f.finding_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">
                      {f.finding_number}
                    </td>
                    <td className="px-4 py-4 text-[12px] text-kfl-text">
                      {f.area}
                    </td>
                    <td className="px-4 py-4">
                      <span className={levelClass(f.level)}>{`Level ${f.level}`}</span>
                    </td>
                    <td className="px-4 py-4 text-[12px] text-kfl-text line-clamp-1">
                      {f.title}
                    </td>
                    <td className="px-4 py-4">
                      <span className={statusClass(f.status)}>
                        {f.status.replace(/_/g, " ").toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right text-sm">
                      <button
                        type="button"
                        className="text-xs text-kfl-blue underline"
                        onClick={() => navigate(`/audit-findings/${encodeURIComponent(f.finding_id)}`)}
                        aria-label={`View details for finding ${f.finding_number}`}
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-kfl-border p-4">
            <span className="text-sm text-kfl-muted">Page {page + 1}</span>
            <div className="flex gap-2">
              <button type="button" className="app-btn-secondary" disabled={page === 0 || isLoading} onClick={() => setPage((current) => current - 1)}>Previous page</button>
              <button type="button" className="app-btn-secondary" disabled={findings.length < pageSize || isLoading} onClick={() => setPage((current) => current + 1)}>Next page</button>
            </div>
          </div>
          </>
        )}
      </section>
    </div>
  );
}
