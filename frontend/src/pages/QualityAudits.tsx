import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { ClipboardCheck, Wrench } from "lucide-react";
import { useToast } from "../components/ui/Toast";
import FormField from "../components/ui/FormField";
import { CorrectiveActionsModal } from "../components/ui/modals/CorrectiveActionsModal";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export function QualityAudits() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const [showCarModal, setShowCarModal] = useState(false);
  const { data: audits = [], isLoading } = useQuery({
    queryKey: ["quality-audits"],
    queryFn: () => api.get("/p1/quality-audits").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [auditError, setAuditError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const filteredAudits = useMemo(() => audits.filter((audit: any) => {
    const query = search.trim().toLowerCase();
    return (!query || [audit.audit_id, audit.title, audit.audit_type, audit.scope].some((value) => String(value ?? "").toLowerCase().includes(query))) &&
      (!statusFilter || audit.status === statusFilter);
  }), [audits, search, statusFilter]);

  const { errors: qaFieldErrors, isValid: qaIsValid } = useValidation(
    { title },
    {
      title: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/quality-audits", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quality-audits"] });
      setShowForm(false);
      setDirty(false);
      setTitle("");
      setAuditError("");
      toast({ title: "Audit created", message: "The new quality audit has been scheduled.", type: "success" });
    },
    onError: () => {
      setAuditError("Failed to create audit. Please try again.");
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
        {hasPermission("safety:create") && <Button
          onClick={() => setShowForm(!showForm)}
          variant="default"
          size="sm"
        >
          <ClipboardCheck size={16} /> {showForm ? "Cancel" : "New Audit"}
        </Button>}
        {hasPermission("safety:create") && <Button
          onClick={() => setShowCarModal(true)}
          variant="outline"
          size="sm"
        >
          <Wrench size={16} /> Create CAR
        </Button>}
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
            <Input id="search_audits_95" name="search_audits" type="search" aria-label="Search quality audits" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search audits…" className="pl-9 relative z-10" />
          </div>
          <select id="select_field_97" name="status" aria-label="Filter quality audits by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-full md:w-auto">
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
              <Button variant="outline" size="sm" onClick={() => { setShowForm(false); setDirty(false); }}>
                Cancel
              </Button>
            </div>
            {auditError && (
              <div role="alert" className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {auditError}
              </div>
            )}
            <FormField htmlFor="audit_title_119" label="Audit title" hint="Use the audit scope or activity name." required>
              <Input id="audit_title_150" name="audit_title" aria-describedby="audit_title_150-error" aria-invalid={!!qaFieldErrors.title} className={qaFieldErrors.title ? "border-rose-400" : ""} placeholder="Audit title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {qaFieldErrors.title && <p id="audit_title_150-error" className="text-[11px] text-rose-700 mt-1">{qaFieldErrors.title}</p>}
            </FormField>
            <Button
              disabled={!qaIsValid || createMutation.isPending}
              onClick={() => {
                setAuditError("");
                createMutation.mutate({ title, auditor_id: "u-quality" });
              }}
              variant="default"
              size="sm"
              className="w-full disabled:opacity-60"
            >
              {createMutation.isPending ? "Creating…" : "Create Audit"}
            </Button>
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
        ) : filteredAudits.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">No quality audits match these filters.</div>
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
                {filteredAudits.map((a: any) => (
                  <tr key={a.audit_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{a.audit_id}</td>
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{a.title}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.audit_type}</td>
                    <td className="px-4 py-4"><Badge variant={a.status === "completed" ? "default" : a.status === "in_progress" ? "secondary" : a.status === "cancelled" ? "destructive" : "outline"} className={`badge ${a.status === "completed" ? "bg-kfl-status-info-bg text-kfl-status-info" : a.status === "in_progress" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : a.status === "cancelled" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{a.status}</Badge></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.findings_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <CorrectiveActionsModal open={showCarModal} onClose={() => setShowCarModal(false)} />
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
                    <td className="px-4 py-4"><Badge variant={c.status === "closed" || c.status === "verified" ? "default" : c.status === "in_progress" ? "secondary" : c.status === "overdue" ? "destructive" : "outline"} className={`badge ${c.status === "closed" || c.status === "verified" ? "bg-kfl-status-info-bg text-kfl-status-info" : c.status === "in_progress" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : c.status === "overdue" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{c.status}</Badge></td>
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
