import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { auditApi } from "../api/audit";
import type { AuditReport } from "../api/audit";
import { FileText, Plus, RefreshCw } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useAuth } from "../auth/AuthContext";
import { AuditReportImportWorkflow } from "../components/AuditReportImportWorkflow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

const AUDIT_REPORT_PAGE_SIZE = 50;
const AUDIT_REPORT_STATUSES = ["open", "in_progress", "closed", "cancelled"];

export function AuditReports() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const todayUtc = new Date().toISOString().slice(0, 10);
  const [showForm, setShowForm] = useState(false);
  const [auditNumber, setAuditNumber] = useState("");
  const [auditDate, setAuditDate] = useState("");
  const [auditorId, setAuditorId] = useState("");
  const [auditeeId, setAuditeeId] = useState("");
  const [scope, setScope] = useState("");
  const [regulatoryBasis, setRegulatoryBasis] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [reportOffset, setReportOffset] = useState(0);
  const [mutationError, setMutationError] = useState("");
  const {
    data: fetchedReports = [],
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["audit-reports", reportOffset, search, statusFilter],
    queryFn: () => auditApi.listAuditReports({
      limit: AUDIT_REPORT_PAGE_SIZE + 1,
      offset: reportOffset,
      search: search.trim() || undefined,
      status: statusFilter || undefined,
    }),
  });
  const hasNextPage = fetchedReports.length > AUDIT_REPORT_PAGE_SIZE;
  const reports = fetchedReports.slice(0, AUDIT_REPORT_PAGE_SIZE);

  const createMutation = useMutation({
    mutationFn: (data: any) => auditApi.createAuditReport(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["audit-reports"] });
      setReportOffset(0);
      setShowForm(false);
      setAuditNumber("");
      setAuditDate("");
      setAuditorId("");
      setAuditeeId("");
      setScope("");
      setRegulatoryBasis("");
      setMutationError("");
    },
    onError: () => setMutationError("Unable to create audit report. Please check the details and try again."),
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Audit Management</div>
          <h1 className="app-title">Audit Reports</h1>
          <p className="app-subtitle">
            View and manage audit engagements and their findings.
          </p>
        </div>
        {hasPermission("audit_report:create") && <Button
          onClick={() => setShowForm(!showForm)}
          variant="default"
          size="sm"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Audit"}
        </Button>}
        <Button
          onClick={() => qc.invalidateQueries({ queryKey: ["audit-reports"] })}
          variant="outline"
          size="sm"
        >
          <RefreshCw size={16} /> Refresh
        </Button>
      </header>

      {showForm && (
        <div className="app-surface p-5 mb-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="app-label mb-1">New Audit Engagement</div>
              <p className="text-xs text-kfl-muted">
                Record a new internal or external audit engagement.
              </p>
            </div>
            <Button
              type="button"
              onClick={() => { setShowForm(false); setMutationError(""); }}
              variant="outline"
              size="sm"
            >
              Cancel
            </Button>
          </div>
          {mutationError && <p role="alert" className="mb-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">{mutationError}</p>}
          <div className="space-y-3 mb-4">
            <FormField
              htmlFor="audit_number"
              label="Audit Number"
              hint="e.g. SS-KFL-SEP 2026"
              required
            >
              <Input
                id="audit_number"
                name="audit_number"
                placeholder="SS-KFL-SEP 2026"
                value={auditNumber}
                onChange={(e) => setAuditNumber(e.target.value)}
              />
            </FormField>
            <FormField
              htmlFor="audit_date"
              label="Audit Date"
              hint="Historical source audits must use the provenance import workflow."
              required
            >
              <Input
                id="audit_date"
                name="audit_date"
                type="date"
                min={todayUtc}
                value={auditDate}
                onChange={(e) => setAuditDate(e.target.value)}
              />
            </FormField>
            <FormField htmlFor="auditor_id" label="Auditor User ID" hint="Must be an active independent_auditor account." required>
              <Input id="auditor_id" name="auditor_id" value={auditorId} onChange={(event) => setAuditorId(event.target.value)} autoComplete="off" />
            </FormField>
            <FormField htmlFor="auditee_id" label="Auditee User ID" hint="Must be an active account and different from the auditor." required>
              <Input id="auditee_id" name="auditee_id" value={auditeeId} onChange={(event) => setAuditeeId(event.target.value)} autoComplete="off" />
            </FormField>
            <FormField htmlFor="scope" label="Scope" hint="e.g. Safety and Security">
              <Input
                id="scope"
                name="scope"
                placeholder="Safety and Security"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
              />
            </FormField>
            <FormField htmlFor="regulatory_basis" label="Regulatory Basis">
              <Input
                id="regulatory_basis"
                name="regulatory_basis"
                placeholder="e.g. KCARs 2018, KCAA CL: O-SMS003"
                value={regulatoryBasis}
                onChange={(e) => setRegulatoryBasis(e.target.value)}
              />
            </FormField>
          </div>
          <Button
            type="button"
            disabled={createMutation.isPending || !auditNumber.trim() || !auditDate || auditDate < todayUtc || !auditorId.trim() || !auditeeId.trim() || auditorId.trim() === auditeeId.trim()}
            onClick={() =>
              createMutation.mutate({
                audit_number: auditNumber,
                audit_date: auditDate,
                auditor_id: auditorId.trim(),
                auditee_id: auditeeId.trim(),
                scope: scope || undefined,
                regulatory_basis: regulatoryBasis || undefined,
              })
            }
            variant="default"
            size="sm"
            className="w-full disabled:opacity-60"
          >
            {createMutation.isPending ? "Creating…" : "Create Audit"}
          </Button>
        </div>
      )}

      {(hasPermission("audit_report:import") || hasPermission("audit_report:provenance_verify")) && (
        <AuditReportImportWorkflow />
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <Input type="search" id="audit-report-search" name="search" aria-label="Search audit reports" value={search} onChange={(event) => { setSearch(event.target.value); setReportOffset(0); }} placeholder="Search audit reports…" />
          </div>
          <Select onValueChange={(e) => { setStatusFilter(e); setReportOffset(0); }}>
            <SelectTrigger id="audit-report-status" name="status" aria-label="Filter audit reports by status">
              <SelectValue placeholder={statusFilter || "All statuses"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All statuses</SelectItem>
              {AUDIT_REPORT_STATUSES.map((status) => <SelectItem key={status} value={status}>{status.replace(/_/g, " ")}</SelectItem>)}
            </SelectContent>
          </Select>
          <div className="text-sm font-semibold text-kfl-text">Audit Reports</div>
        </div>

        {isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="text-sm font-semibold text-rose-800">Unable to load audit reports.</p>
            <Button onClick={() => void refetch()} variant="outline" size="sm" className="mt-3" aria-label="Retry loading audit reports">
              Retry
            </Button>
          </div>
        ) : isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">
            Loading audit reports…
          </div>
        ) : reports.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <FileText size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">
              {search.trim() || statusFilter ? "No audit reports match these filters." : "No audit reports recorded."}
            </p>
            {!search.trim() && !statusFilter && <p className="mt-1 text-xs text-kfl-muted">
              Create your first audit engagement to begin tracking findings.
            </p>}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Audit Number
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Audit Date
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">
                    Scope
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
                {reports.map((r: AuditReport) => (
                  <tr key={r.audit_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">
                      {r.audit_number}
                    </td>
                    <td className="px-4 py-4 text-[12px] text-kfl-text">
                      {r.audit_date}
                    </td>
                    <td className="px-4 py-4 text-[12px] text-kfl-text">
                      {r.scope || "—"}
                    </td>
                    <td className="px-4 py-4">
                      <Badge variant={r.status === "open" ? "secondary" : "default"} className={`badge ${r.status === "open" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>
                        {r.status.replace(/_/g, " ").toUpperCase()}
                      </Badge>
                    </td>
                    <td className="px-4 py-4 text-right text-sm">
                      <div className="flex items-center justify-end gap-3">
                        {r.evidence_file && hasPermission("audit_report:read") && <a
                          href={`/api/p3/audit-reports/${encodeURIComponent(r.audit_id)}/evidence`}
                          className="text-xs text-kfl-blue underline"
                          aria-label={`Download Evidence for ${r.audit_number}`}
                        >
                          Download Evidence
                        </a>}
                        {hasPermission("audit_finding:read") && <button
                          type="button"
                          className="text-xs text-kfl-blue underline"
                          onClick={() => navigate(`/audit-findings?audit_id=${encodeURIComponent(r.audit_id)}`)}
                          aria-label={`View Findings for ${r.audit_number}`}
                        >
                          View Findings
                        </button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!isError && !isLoading && (reportOffset > 0 || hasNextPage) && (
          <footer className="flex items-center justify-between gap-3 border-t border-kfl-border p-4">
            <span role="status" className="text-xs text-kfl-muted">
              Showing {reportOffset + 1}–{reportOffset + reports.length}
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label="Previous audit reports"
                disabled={reportOffset === 0 || isFetching}
                onClick={() => setReportOffset(Math.max(0, reportOffset - AUDIT_REPORT_PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label="Next audit reports"
                disabled={!hasNextPage || isFetching}
                onClick={() => setReportOffset(reportOffset + AUDIT_REPORT_PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </footer>
        )}
      </section>
    </div>
  );
}
