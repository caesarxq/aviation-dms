import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, CheckCircle2, Users, Search, ClipboardList } from "lucide-react";
import { qualityAuditApi } from "../api/audit";
import { useAuth } from "../auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { useToast } from "../components/ui/Toast";
import { useValidation } from "../utils/validation";
import FormField from "../components/ui/FormField";

const AUDIT_PAGE_SIZE = 50;
const AUDIT_STATUSES = ["planned", "in_progress", "completed", "cancelled"];
const RESOURCE_TYPES = ["data_source", "interview", "document", "checklist", "other"];
const RESOURCE_TYPE_LABELS: Record<string, string> = {
  data_source: "Data Source",
  interview: "Interview",
  document: "Document",
  checklist: "Checklist",
  other: "Other",
};

export function AuditPlanning() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const { toast } = useToast();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [viewing, setViewing] = useState<string | null>(null);
  const [showResourceForm, setShowResourceForm] = useState(false);
  const [resourceType, setResourceType] = useState("data_source");
  const [resourceName, setResourceName] = useState("");
  const [resourceDescription, setResourceDescription] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newAuditType, setNewAuditType] = useState("internal");
  const [newScope, setNewScope] = useState("");
  const [newAuditorId, setNewAuditorId] = useState("");
  const [newAuditeeId, setNewAuditeeId] = useState("");
  const [newPlannedDate, setNewPlannedDate] = useState("");
  const [newChecklistItems, setNewChecklistItems] = useState("");
  const [createdAuditId, setCreatedAuditId] = useState<string | null>(null);
  const [createError, setCreateError] = useState("");
  const todayUtc = new Date().toISOString().slice(0, 10);

  const {
    data: audits = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["quality-audits-planning", offset, search, statusFilter],
    queryFn: () =>
      qualityAuditApi.listQualityAudits({
        limit: AUDIT_PAGE_SIZE + 1,
        offset,
        status: statusFilter || undefined,
      }),
  });

  const hasNextPage = audits.length > AUDIT_PAGE_SIZE;
  const pageAudits = audits.slice(0, AUDIT_PAGE_SIZE);

  const selectedAudit = audits.find((a) => a.audit_id === viewing);

  const {
    data: resources = [],
    isLoading: resourcesLoading,
  } = useQuery({
    queryKey: ["audit-resources", viewing ?? ""],
    queryFn: () => qualityAuditApi.listAuditResources(viewing!),
    enabled: !!viewing,
  });

  const {
    isValid: createIsValid,
  } = useValidation(
    { title: newTitle },
    { title: { required: true, minLength: 2 } }
  );

  const createMutation = useMutation({
    mutationFn: async ({ audit, checklistItems }: { audit: any; checklistItems: string[] }) => {
      const createdAudit = await qualityAuditApi.createQualityAudit(audit);
      if (checklistItems.length === 0) return { audit: createdAudit, checklistSaved: true };
      try {
        await qualityAuditApi.createAuditResource(createdAudit.audit_id, {
          resource_type: "checklist",
          resource_name: "Audit checklist",
          description: checklistItems.map((item) => `☐ ${item}`).join("\n"),
        });
        return { audit: createdAudit, checklistSaved: true };
      } catch {
        return { audit: createdAudit, checklistSaved: false };
      }
    },
    onSuccess: ({ audit, checklistSaved }) => {
      qc.invalidateQueries({ queryKey: ["quality-audits-planning"] });
      if (!checklistSaved) {
        setCreatedAuditId(audit.audit_id);
        setCreateError("");
        toast({ title: "Audit plan created; checklist needs retry", message: `Plan ${audit.audit_id} was saved. Retry the checklist before leaving this page.`, type: "warning", duration: 10000 });
        return;
      }
      setShowCreateForm(false);
      setNewTitle("");
      setNewAuditType("internal");
      setNewScope("");
      setNewAuditorId("");
      setNewAuditeeId("");
      setNewPlannedDate("");
      setNewChecklistItems("");
      setCreatedAuditId(null);
      setCreateError("");
      toast({ title: "Audit planned", message: "The audit has been scheduled with its checklist.", type: "success" });
    },
    onError: () => setCreateError("Failed to create audit plan. Please try again."),
  });

  const retryChecklistMutation = useMutation({
    mutationFn: () => {
      if (!createdAuditId) throw new Error("No audit plan is awaiting a checklist");
      const checklistItems = newChecklistItems.split("\n").map((item) => item.trim()).filter(Boolean);
      return qualityAuditApi.createAuditResource(createdAuditId, {
        resource_type: "checklist",
        resource_name: "Audit checklist",
        description: checklistItems.map((item) => `☐ ${item}`).join("\n"),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["audit-resources", createdAuditId ?? ""] });
      qc.invalidateQueries({ queryKey: ["quality-audits-planning"] });
      setShowCreateForm(false);
      setNewTitle("");
      setNewAuditType("internal");
      setNewScope("");
      setNewAuditorId("");
      setNewAuditeeId("");
      setNewPlannedDate("");
      setNewChecklistItems("");
      setCreatedAuditId(null);
      toast({ title: "Audit checklist saved", message: "The plan and checklist are ready.", type: "success" });
    },
    onError: () => toast({ title: "Checklist retry failed", message: "The audit plan remains saved; retry the checklist again.", type: "error" }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      qualityAuditApi.updateQualityAudit(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quality-audits-planning"] });
      qc.invalidateQueries({ queryKey: ["quality-audit-detail", viewing] });
      toast({ title: "Audit updated", message: "Audit plan changes saved.", type: "success" });
    },
    onError: () => toast({ title: "Update failed", message: "Could not save changes.", type: "error" }),
  });

  const createResourceMutation = useMutation({
    mutationFn: ({ auditId, data }: { auditId: string; data: any }) =>
      qualityAuditApi.createAuditResource(auditId, data),
    onSuccess: (_, { auditId }) => {
      qc.invalidateQueries({ queryKey: ["quality-audit-detail", auditId] });
      setShowResourceForm(false);
      setResourceType("data_source");
      setResourceName("");
      setResourceDescription("");
      toast({ title: "Resource added", message: "Audit resource recorded.", type: "success" });
    },
    onError: () => toast({ title: "Failed", message: "Could not add resource.", type: "error" }),
  });

  const updateResourceMutation = useMutation({
    mutationFn: ({ auditId, resourceId, data }: { auditId: string; resourceId: string; data: any }) =>
      qualityAuditApi.updateAuditResource(auditId, resourceId, data),
    onSuccess: () => {
      toast({ title: "Resource updated", type: "success" });
    },
    onError: () => toast({ title: "Failed", message: "Could not update resource.", type: "error" }),
  });

  const deleteResourceMutation = useMutation({
    mutationFn: ({ auditId, resourceId }: { auditId: string; resourceId: string }) =>
      qualityAuditApi.deleteAuditResource(auditId, resourceId),
    onSuccess: () => {
      toast({ title: "Resource removed", type: "success" });
    },
  });

  const filteredAudits = useMemo(() =>
    pageAudits.filter((a) => {
      const q = search.trim().toLowerCase();
      return (
        (!q ||
          [a.audit_id, a.title, a.audit_type, a.scope].some(
            (v) => String(v ?? "").toLowerCase().includes(q)
          )) &&
        (!statusFilter || a.status === statusFilter)
      );
    }),
    [pageAudits, search, statusFilter]
  );

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      planned: "bg-kfl-status-warning-bg text-kfl-status-warning",
      in_progress: "bg-kfl-status-info-bg text-kfl-status-info",
      completed: "bg-kfl-status-success-bg text-kfl-status-success",
      cancelled: "bg-kfl-status-danger-bg text-kfl-status-danger",
    };
    return (
      <Badge variant="outline" className={`badge ${map[s] || "bg-kfl-surface-subtle text-kfl-muted"}`}>
        {s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
      </Badge>
    );
  };

  if (!viewing) {
    return (
      <div className="app-page">
        <header className="app-page-header">
          <div>
            <div className="app-eyebrow">Audit Management</div>
            <h1 className="app-title">Audit Planning</h1>
            <p className="app-subtitle">
              Plan, schedule, and track audits across Quality, Safety, and Security.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {hasPermission("safety:create") && (
              <Button
                onClick={() => setShowCreateForm(true)}
                variant="default"
                size="sm"
              >
                <Plus size={16} /> {showCreateForm ? "Cancel" : "Plan Audit"}
              </Button>
            )}
            <Button
              onClick={() => qc.invalidateQueries({ queryKey: ["quality-audits-planning"] })}
              variant="outline"
              size="sm"
            >
              <RefreshCw size={16} /> Refresh
            </Button>
          </div>
        </header>

        {showCreateForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">Plan New Audit</div>
                <p className="text-xs text-kfl-muted">
                  Schedule an audit, define its scope, and assign resources.
                </p>
              </div>
              <Button
                type="button"
                onClick={() => { setShowCreateForm(false); setCreateError(""); }}
                variant="outline"
                size="sm"
              >
                Cancel
              </Button>
            </div>
            {createError && (
              <p role="alert" className="mb-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {createError}
              </p>
            )}
            <div className="space-y-3 mb-4">
              <FormField
                htmlFor="plan_title"
                label="Audit Title"
                hint="e.g. Annual Safety Management System Audit"
                required
              >
                <Input
                  id="plan_title"
                  name="plan_title"
                  placeholder="Audit title"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                />
              </FormField>
              <FormField htmlFor="plan_type" label="Audit Type" required>
                <Select value={newAuditType} onValueChange={setNewAuditType}>
                  <SelectTrigger id="plan_type">
                    <SelectValue placeholder={newAuditType} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="internal">Internal</SelectItem>
                    <SelectItem value="external">External</SelectItem>
                    <SelectItem value="regulatory">Regulatory</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              <FormField htmlFor="plan_scope" label="Scope" hint="What will be covered">
                <Input
                  id="plan_scope"
                  name="plan_scope"
                  placeholder="e.g. Flight operations, maintenance records"
                  value={newScope}
                  onChange={(e) => setNewScope(e.target.value)}
                />
              </FormField>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField htmlFor="plan_auditor" label="Auditor User ID" required>
                  <Input
                    id="plan_auditor"
                    name="plan_auditor"
                    placeholder="e.g. u-head-quality"
                    value={newAuditorId}
                    onChange={(e) => setNewAuditorId(e.target.value)}
                    autoComplete="off"
                  />
                </FormField>
                <FormField htmlFor="plan_auditee" label="Auditee User ID">
                  <Input
                    id="plan_auditee"
                    name="plan_auditee"
                    placeholder="e.g. u-head-operations"
                    value={newAuditeeId}
                    onChange={(e) => setNewAuditeeId(e.target.value)}
                    autoComplete="off"
                  />
                </FormField>
              </div>
              <FormField htmlFor="plan_date" label="Planned Date" required>
                <Input
                  id="plan_date"
                  name="plan_date"
                  type="date"
                  min={todayUtc}
                  value={newPlannedDate}
                  onChange={(e) => setNewPlannedDate(e.target.value)}
                />
              </FormField>
              <FormField htmlFor="plan_checklist" label="Checklist items" hint="Enter one inspection or interview point per line. Leave blank if no checklist is needed.">
                <Textarea
                  id="plan_checklist"
                  name="plan_checklist"
                  aria-label="Checklist items"
                  rows={4}
                  placeholder="Review flight records\nInterview operations staff"
                  value={newChecklistItems}
                  onChange={(e) => setNewChecklistItems(e.target.value)}
                  disabled={!!createdAuditId}
                />
              </FormField>
            </div>
            {createdAuditId && (
              <div role="status" className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                <p>Audit plan {createdAuditId} was created, but its checklist was not saved.</p>
                <Button type="button" size="sm" className="mt-2" disabled={retryChecklistMutation.isPending} onClick={() => retryChecklistMutation.mutate()}>
                  {retryChecklistMutation.isPending ? "Saving checklist…" : "Retry checklist"}
                </Button>
              </div>
            )}
            <Button
              type="button"
              disabled={createMutation.isPending || !!createdAuditId || !newTitle.trim() || !createIsValid}
              onClick={() => {
                if (!newTitle.trim() || createdAuditId) return;
                const checklistItems = newChecklistItems.split("\n").map((item) => item.trim()).filter(Boolean);
                createMutation.mutate({
                  audit: {
                    title: newTitle.trim(),
                    audit_type: newAuditType,
                    scope: newScope.trim() || undefined,
                    auditor_id: newAuditorId.trim(),
                    auditee_id: newAuditeeId.trim() || undefined,
                    planned_date: newPlannedDate || undefined,
                  },
                  checklistItems,
                });
              }}
              variant="default"
              size="sm"
              className="w-full disabled:opacity-60"
            >
              {createMutation.isPending ? "Creating…" : "Create Audit Plan"}
            </Button>
          </div>
        )}

        <section className="app-surface overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between md:gap-4">
            <div className="relative min-w-0 flex-1 md:max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-kfl-muted" />
              <Input
                type="search"
                id="audit-planning-search"
                name="search"
                aria-label="Search audit plans"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
                placeholder="Search audit plans…"
                className="pl-9 relative z-10"
              />
            </div>
            <div className="md:shrink-0">
              <Select
                onValueChange={(e) => { setStatusFilter(e); setOffset(0); }}
              >
              <SelectTrigger id="audit-planning-status" name="status" aria-label="Filter audit plans by status">
                <SelectValue placeholder={statusFilter || "All statuses"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All statuses</SelectItem>
                {AUDIT_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            </div>
            <div className="text-sm font-semibold text-kfl-text md:shrink-0">Audit Plans</div>
          </div>

          {isError ? (
            <div className="p-10 text-center" role="alert">
              <p className="text-sm font-semibold text-rose-800">Unable to load audit plans.</p>
              <Button onClick={() => void refetch()} variant="outline" size="sm" className="mt-3">
                Retry
              </Button>
            </div>
          ) : isLoading ? (
            <div className="p-10 text-center text-sm text-kfl-muted">Loading audit plans…</div>
          ) : filteredAudits.length === 0 ? (
            <div className="app-surface border-dashed p-10 text-center">
              <ClipboardList size={26} className="mx-auto mb-2 text-kfl-muted" />
              <p className="text-sm font-bold text-kfl-text">
                {search.trim() || statusFilter ? "No audit plans match these filters." : "No audit plans recorded."}
              </p>
              {!search.trim() && !statusFilter && (
                <p className="mt-1 text-xs text-kfl-muted">
                  Create your first audit plan to begin tracking audits across the organization.
                </p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Scope</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Planned</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Findings</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {filteredAudits.map((a) => (
                    <tr
                      key={a.audit_id}
                      className="transition hover:bg-kfl-surface-subtle group cursor-pointer"
                      onClick={() => setViewing(a.audit_id)}
                    >
                      <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{a.audit_id}</td>
                      <td className="px-4 py-4 text-sm font-medium text-kfl-text">{a.title}</td>
                      <td className="px-4 py-4 text-[12px] text-kfl-secondary">{a.audit_type.replace(/_/g, " ").toUpperCase()}</td>
                      <td className="px-4 py-4 text-[12px] text-kfl-secondary">{a.scope || "—"}</td>
                      <td className="px-4 py-4 text-[12px] text-kfl-secondary">{a.planned_date || "—"}</td>
                      <td className="px-4 py-4">{statusBadge(a.status)}</td>
                      <td className="px-4 py-4 text-[12px] text-kfl-secondary text-right">{a.findings_count}</td>
                      <td className="px-4 py-4 text-right text-sm">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            className="text-xs text-kfl-blue underline"
                            onClick={(e) => {
                              e.stopPropagation();
                              setViewing(a.audit_id);
                            }}
                            aria-label={`View audit plan ${a.audit_id}`}
                          >
                            Open
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!isError && !isLoading && (offset > 0 || hasNextPage) && (
            <footer className="flex items-center justify-between gap-3 border-t border-kfl-border p-4">
              <span role="status" className="text-xs text-kfl-muted">
                Showing {offset + 1}–{offset + pageAudits.length}
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={offset === 0 || isLoading}
                  onClick={() => setOffset(Math.max(0, offset - AUDIT_PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!hasNextPage || isLoading}
                  onClick={() => setOffset(offset + AUDIT_PAGE_SIZE)}
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

  if (!selectedAudit) {
    return <div className="app-page p-10 text-center text-sm text-kfl-muted">Loading audit…</div>;
  }

  const handleBackToList = () => {
    setViewing(null);
    setShowResourceForm(false);
  };

  const handleStatusChange = (newStatus: string) => {
    if (!selectedAudit) return;
    updateMutation.mutate({
      id: selectedAudit.audit_id,
      data: { status: newStatus },
    });
  };

  const handleResultChange = (value: string) => {
    if (!selectedAudit) return;
    updateMutation.mutate({
      id: selectedAudit.audit_id,
      data: { overall_result: value },
    });
  };

  const handleReportChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (!selectedAudit) return;
    updateMutation.mutate({
      id: selectedAudit.audit_id,
      data: { report: e.target.value },
    });
  };

  const handleResourceSubmit = () => {
    if (!selectedAudit || !resourceName.trim()) return;
    createResourceMutation.mutate({
      auditId: selectedAudit.audit_id,
      data: {
        resource_type: resourceType,
        resource_name: resourceName.trim(),
        description: resourceDescription.trim() || undefined,
      },
    });
  };

  const handleResourceStatusChange = (resourceId: string, newStatus: string) => {
    if (!selectedAudit) return;
    updateResourceMutation.mutate({
      auditId: selectedAudit.audit_id,
      resourceId,
      data: { status: newStatus },
    });
  };

  const handleDeleteResource = (resourceId: string) => {
    if (!selectedAudit || !confirm("Remove this resource?")) return;
    deleteResourceMutation.mutate({
      auditId: selectedAudit.audit_id,
      resourceId,
    });
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <button
            type="button"
            onClick={handleBackToList}
            className="inline-flex items-center gap-2 text-sm font-medium text-kfl-blue underline mb-2"
          >
            <Users size={14} /> Back to Audit Plans
          </button>
          <div>
            <div className="app-eyebrow">Audit Planning</div>
            <h1 className="app-title">{selectedAudit.title}</h1>
            <p className="app-subtitle">
              {selectedAudit.audit_id} — {selectedAudit.audit_type.replace(/_/g, " ").toUpperCase()} Audit
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {selectedAudit.status === "planned" && hasPermission("safety:update") && (
            <Button
              onClick={() => handleStatusChange("in_progress")}
              variant="default"
              size="sm"
            >
              <CheckCircle2 size={16} /> Start Audit
            </Button>
          )}
          {selectedAudit.status === "in_progress" && hasPermission("safety:update") && (
            <Button
              onClick={() => handleStatusChange("completed")}
              variant="default"
              size="sm"
            >
              <CheckCircle2 size={16} /> Complete Audit
            </Button>
          )}
          {hasPermission("safety:update") && (
            <Button
              onClick={() => handleStatusChange("cancelled")}
              variant="outline"
              size="sm"
            >
              Cancel Audit
            </Button>
          )}
        </div>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Status</div>
          <div className="mt-2">{statusBadge(selectedAudit.status)}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Findings</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{selectedAudit.findings_count}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Planned Date</div>
          <div className="mt-2 text-sm text-kfl-secondary">{selectedAudit.planned_date || "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Actual Date</div>
          <div className="mt-2 text-sm text-kfl-secondary">{selectedAudit.actual_date || "—"}</div>
        </div>
      </section>

      <section className="mb-6 app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Audit Details</div>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-kfl-muted mb-1">Auditor</div>
              <div className="text-sm font-medium text-kfl-text">{selectedAudit.auditor_id}</div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-kfl-muted mb-1">Auditee</div>
              <div className="text-sm font-medium text-kfl-text">{selectedAudit.auditee_id || "—"}</div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-kfl-muted mb-1">Overall Result</div>
              <Select
                value={selectedAudit.overall_result || ""}
                onValueChange={handleResultChange}
              >
                <SelectTrigger>
                  <SelectValue placeholder={selectedAudit.overall_result || "Not assessed"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="effective">Effective</SelectItem>
                  <SelectItem value="partially_effective">Partially Effective</SelectItem>
                  <SelectItem value="ineffective">Ineffective</SelectItem>
                  <SelectItem value="not_assessed">Not Assessed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-kfl-muted mb-1">Audit Report</div>
              <Textarea
                value={selectedAudit.report || ""}
                onChange={handleReportChange}
                placeholder="Summarize audit conclusions, evidence reviewed, and overall conclusion…"
                rows={3}
                className="w-full"
              />
            </div>
          </div>
        </div>
      </section>

      <section className="mb-6 app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Audit Resources</div>
          <div className="flex gap-2">
            {hasPermission("safety:create") && (
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={() => setShowResourceForm(true)}
              >
                <Plus size={14} /> Add Resource
              </Button>
            )}
          </div>
        </div>

        {showResourceForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">Add Audit Resource</div>
                <p className="text-xs text-kfl-muted">
                  Record a data source, interview, or document to be reviewed during this audit.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowResourceForm(false)}
              >
                Cancel
              </Button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <FormField htmlFor="resource_type" label="Resource Type" required>
                <Select value={resourceType} onValueChange={setResourceType}>
                  <SelectTrigger id="resource_type">
                    <SelectValue placeholder={RESOURCE_TYPE_LABELS[resourceType]} />
                  </SelectTrigger>
                  <SelectContent>
                    {RESOURCE_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {RESOURCE_TYPE_LABELS[t]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <FormField htmlFor="resource_name" label="Resource Name" hint="e.g. Flight ops manual, Chief Pilot interview" required>
                <Input
                  id="resource_name"
                  name="resource_name"
                  placeholder="Resource name"
                  value={resourceName}
                  onChange={(e) => setResourceName(e.target.value)}
                />
              </FormField>
              <FormField htmlFor="resource_desc" label="Description">
                <Input
                  id="resource_desc"
                  name="resource_desc"
                  placeholder="Optional details"
                  value={resourceDescription}
                  onChange={(e) => setResourceDescription(e.target.value)}
                />
              </FormField>
            </div>
            <Button
              type="button"
              disabled={createResourceMutation.isPending || !resourceName.trim()}
              onClick={handleResourceSubmit}
              variant="default"
              size="sm"
              className="w-full disabled:opacity-60"
            >
              {createResourceMutation.isPending ? "Adding…" : "Add Resource"}
            </Button>
          </div>
        )}

        <div className="p-5">
          {resourcesLoading ? (
            <div className="p-10 text-center text-sm text-kfl-muted">Loading resources…</div>
          ) : resources.length === 0 ? (
            <div className="app-surface border-dashed p-10 text-center">
              <Users size={26} className="mx-auto mb-2 text-kfl-muted" />
              <p className="text-sm font-bold text-kfl-text">No resources planned.</p>
              <p className="mt-1 text-xs text-kfl-muted">
                Add data sources, interviews, or documents that will be reviewed during this audit.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Resource</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Description</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {resources.map((r) => (
                    <tr key={r.resource_id} className="transition hover:bg-kfl-surface-subtle">
                      <td className="px-4 py-4 text-[12px] text-kfl-secondary">{RESOURCE_TYPE_LABELS[r.resource_type] || r.resource_type}</td>
                      <td className="px-4 py-4 text-sm font-medium text-kfl-text">{r.resource_name}</td>
                      <td className="px-4 py-4 text-[12px] text-kfl-secondary">{r.description || "—"}</td>
                      <td className="px-4 py-4">
                        <Select
                          value={r.status}
                          onValueChange={(val) => handleResourceStatusChange(r.resource_id, val)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder={r.status} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="pending">Pending</SelectItem>
                            <SelectItem value="completed">Completed</SelectItem>
                            <SelectItem value="not_required">Not Required</SelectItem>
                          </SelectContent>
                        </Select>
                      </td>
                      <td className="px-4 py-4 text-right">
                        <button
                          type="button"
                          className="text-xs text-rose-600 underline"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteResource(r.resource_id);
                          }}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default AuditPlanning;
