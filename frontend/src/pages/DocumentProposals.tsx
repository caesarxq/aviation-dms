import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import DOMPurify from "dompurify";
import api from "../api/client";
import { listDocuments } from "../api/documents";
import { Plus, Check, X, ArrowUpRight } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

function ProposalExcerpt({ label, html, fallback, tone }: { label: string; html?: string; fallback?: string; tone: "removed" | "added" }) {
  const safeHtml = html ? DOMPurify.sanitize(html) : "";
  return (
    <div className={`rounded-md p-2 text-sm ${tone === "removed" ? "bg-kfl-status-danger-bg/20 text-kfl-status-danger" : "bg-kfl-status-success-bg/20 text-kfl-status-success"}`}>
      <strong>{label}:</strong>
      {safeHtml ? <div className="mt-1 leading-6" dangerouslySetInnerHTML={{ __html: safeHtml }} /> : <span className="ml-1">{fallback || "—"}</span>}
    </div>
  );
}

export function DocumentProposals() {
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const canUpdate = hasPermission("document:update");
  const canPropose = hasPermission("document:propose");
  const canApproveOrReject = canUpdate || hasPermission("document:approve");
  const canOpenAffectedSection = canPropose || canUpdate;
  const canPublish = hasPermission("document:publish");
  const qc = useQueryClient();
  const [docId, setDocId] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [filterStatus, setFilterStatus] = useState("");
  const [form, setForm] = useState({
    proposal_type: "word", target_ref: "", original_text: "", proposed_text: "",
    rationale: "", severity: "minor",
  });
  const [proposalError, setProposalError] = useState("");

  const { errors: proposalFieldErrors, isValid: proposalIsValid } = useValidation(
    { target_ref: form.target_ref, proposed_text: form.proposed_text, severity: form.severity },
    {
      target_ref: { required: true, minLength: 2 },
      proposed_text: { required: true, minLength: 2 },
      severity: { required: true },
    }
  );

  const { data: docs = [] } = useQuery({
    queryKey: ["documents"],
    queryFn: () => listDocuments().then((page) => page.data),
  });

  useUnsavedChanges(showForm && dirty);

  const { data: proposals = [], isLoading } = useQuery({
    queryKey: ["proposals", docId, filterStatus],
    queryFn: () => {
      if (!docId) return Promise.resolve([]);
      const params = filterStatus ? `?status=${filterStatus}` : "";
      return api.get(`/p2/documents/${docId}/proposals${params}`).then((r: any) => r.data);
    },
    enabled: !!docId,
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post(`/p2/documents/${docId}/proposals`, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proposals"] });
      setShowForm(false);
      setDirty(false);
      setProposalError("");
      setForm({
        proposal_type: "word", target_ref: "", original_text: "", proposed_text: "",
        rationale: "", severity: "minor",
      });
      toast({ title: "Proposal submitted", message: "The document change proposal has been recorded.", type: "success" });
    },
    onError: () => {
      setProposalError("Failed to submit proposal. Please check your entries and try again.");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/p2/proposals/${id}`, data).then((r: any) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proposals"] }),
  });

  const applyMutation = useMutation({
    mutationFn: (id: string) => api.post(`/p2/proposals/${id}/apply`, {}).then((r: any) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proposals"] }),
  });

  const statusColor = (s: string) => {
    if (s === "approved") return "bg-kfl-status-info-bg text-kfl-status-info";
    if (s === "rejected") return "bg-kfl-status-danger-bg text-kfl-status-danger";
    if (s === "submitted" || s === "under_review") return "bg-kfl-status-warning-bg text-kfl-status-warning";
    if (s === "applied") return "bg-kfl-status-info-bg text-kfl-status-info";
    return "bg-kfl-surface-subtle text-kfl-muted";
  };

  const severityColor = (s: string) => {
    if (s === "critical") return "text-kfl-status-danger font-bold";
    if (s === "major") return "text-kfl-status-warning font-semibold";
    return "text-kfl-muted";
  };

  const handleCreate = () => {
    setProposalError("");
    if (!proposalIsValid) {
      setProposalError("Please complete all required fields.");
      return;
    }
    createMutation.mutate(form);
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">Document Proposals</h1>
          <p className="app-subtitle">Review and manage proposed changes to controlled documents.</p>
        </div>
      </header>

      {/* Document selector */}
      <div className="app-surface p-4 mb-4">
        <label className="text-sm font-semibold text-kfl-muted mb-2 block">Select Document</label>
        <select id="docid_115" name="docid" className="border border-kfl-border rounded p-2 text-sm w-full max-w-md" value={docId} onChange={e => setDocId(e.target.value)}>
          <option value="">— Select a document —</option>
          {docs.map((d: any) => <option key={d.document_id} value={d.document_id}>{d.document_id} — {d.title}</option>)}
        </select>
      </div>

      {docId && (
        <>
          <div className="flex gap-2 mb-4">
            {canPropose && (
              <Button onClick={() => setShowForm(true)} variant="default" size="sm" className="flex items-center gap-1 text-sm">
                <Plus size={14} /> New Proposal
              </Button>
            )}
            {["", "draft", "submitted", "approved", "rejected", "applied"].map(s => (
              <Button key={s} variant={filterStatus === s ? "default" : "outline"} size="sm" onClick={() => setFilterStatus(s)}>
                {s || "All"}
              </Button>
            ))}
          </div>

          {/* Proposal Modal */}
          <Modal open={showForm && canPropose} onClose={() => setShowForm(false)} title="Create Proposal" description="Describe one controlled-document change. Target the exact section or block, show the original and proposed text, and explain why the change is needed before submitting it for review.">
            {proposalError && (
              <div role="alert" className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {proposalError}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <FormField htmlFor="proposal_type_142" label="Proposal type" hint="Select the smallest affected document unit.">
                <Select onValueChange={(e) => setForm({ ...form, proposal_type: e })}>
                  <SelectTrigger id="proposal_type_142" name="proposal_type">
                    <SelectValue placeholder={form.proposal_type} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="word">Word</SelectItem>
                    <SelectItem value="line">Line</SelectItem>
                    <SelectItem value="section">Section</SelectItem>
                    <SelectItem value="illustration">Illustration</SelectItem>
                    <SelectItem value="table">Table</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              <FormField htmlFor="severity_145" label="Severity" required>
                <Select onValueChange={(e) => { setForm({ ...form, severity: e }); setDirty(true); }}>
                  <SelectTrigger id="severity_145" name="severity" aria-describedby="severity_145-error">
                    <SelectValue placeholder={form.severity} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="minor">Minor</SelectItem>
                    <SelectItem value="major">Major</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </SelectContent>
                </Select>
                {proposalFieldErrors.severity && <p id="severity_145-error" className="text-[11px] text-kfl-status-danger mt-1">{proposalFieldErrors.severity}</p>}
              </FormField>
              <FormField htmlFor="target_ref_148" label="Target reference" hint="Identify the section, block, line, or illustration affected." required>
                <Input id="target_ref_148" name="target_ref" aria-describedby="target_ref_148-error" aria-invalid={!!proposalFieldErrors.target_ref} className={proposalFieldErrors.target_ref ? "border-rose-400" : ""} placeholder="Section 3.2, line 45" value={form.target_ref} onChange={e => { setForm({ ...form, target_ref: e.target.value }); setDirty(true); }} />
                {proposalFieldErrors.target_ref && <p id="target_ref_148-error" className="text-[11px] text-kfl-status-danger mt-1">{proposalFieldErrors.target_ref}</p>}
              </FormField>
              <FormField htmlFor="original_text_149" label="Original text" hint="Paste the exact current wording.">
                <Input id="original_text_149" name="original_text" placeholder="Current wording" value={form.original_text} onChange={e => { setForm({ ...form, original_text: e.target.value }); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="proposed_text_150" label="Proposed text" hint="Enter the replacement wording.">
                <Input id="proposed_text_150" name="proposed_text" aria-describedby="proposed_text_150-error" aria-invalid={!!proposalFieldErrors.proposed_text} className={proposalFieldErrors.proposed_text ? "border-rose-400" : ""} placeholder="Replacement wording" value={form.proposed_text} onChange={e => { setForm({ ...form, proposed_text: e.target.value }); setDirty(true); }} />
                {proposalFieldErrors.proposed_text && <p id="proposed_text_150-error" className="text-[11px] text-kfl-status-danger mt-1">{proposalFieldErrors.proposed_text}</p>}
              </FormField>
              <FormField htmlFor="rationale_151" label="Rationale" hint="Explain the compliance, safety, or operational reason for the change.">
                <Input id="rationale_151" name="rationale" placeholder="Why is this change needed?" value={form.rationale} onChange={e => { setForm({ ...form, rationale: e.target.value }); setDirty(true); }} />
              </FormField>
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => { setShowForm(false); setDirty(false); }}>
                Cancel
              </Button>
              {canPropose && (
                <Button onClick={handleCreate} variant="default" size="sm" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Saving…" : "Submit Proposal"}
                </Button>
              )}
            </div>
          </Modal>

          {isLoading ? (
            <div className="p-8 text-kfl-muted">Loading proposals…</div>
          ) : proposals.length === 0 ? (
            <div className="app-surface p-8 text-center text-kfl-muted">No proposals found.</div>
          ) : (
            <div className="space-y-3">
              {proposals.map((p: any) => (
                <div key={p.proposal_id} className="app-surface p-4">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <Badge variant={p.status === "approved" ? "default" : p.status === "rejected" ? "destructive" : p.status === "submitted" || p.status === "under_review" ? "secondary" : "outline"} className={`badge ${statusColor(p.status)}`}>{p.status}</Badge>
                      <span className={`ml-2 text-xs ${severityColor(p.severity)}`}>{p.severity}</span>
                      <span className="ml-2 text-xs text-kfl-muted">{p.proposal_type}</span>
                    </div>
                    <span className="text-xs text-kfl-muted font-mono">{p.proposal_id}</span>
                  </div>
                  <div className="text-sm mb-1"><strong>Target:</strong> {p.target_ref}</div>
                  {p.section_heading && <div className="text-xs text-kfl-muted mb-2">Section {p.section_number || "—"} · {p.section_heading} · {p.block_type || "block"} {p.block_index ?? ""}</div>}
                  {(p.changed_token_count || p.grouping_reason) && <div className="mb-2 text-xs text-kfl-muted">Grouped as <strong>{p.proposal_type}</strong> · {p.changed_token_count || 0} token operations · {p.grouping_reason || "structured change"}</div>}
                  <div className="space-y-1">
                    <ProposalExcerpt label="Affected original" html={p.original_excerpt_html} fallback={p.original_text} tone="removed" />
                    <ProposalExcerpt label="Affected proposed" html={p.proposed_excerpt_html} fallback={p.proposed_text} tone="added" />
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    {p.rationale && <div className="text-sm text-kfl-muted"><strong>Rationale:</strong> {p.rationale}</div>}
                    {canOpenAffectedSection && <Link to={`/documents/${p.document_id}/edit?proposal=${encodeURIComponent(p.proposal_id)}&section=${encodeURIComponent(p.anchor_id || "")}`} className="shrink-0 text-xs font-semibold text-kfl-blue hover:underline">Open affected section</Link>}
                  </div>
                  <div className="mt-2 flex gap-2">
                    {canPropose && p.status === "draft" && (
                      <Button onClick={() => updateMutation.mutate({ id: p.proposal_id, data: { status: "submitted" } })} variant="default" size="sm" className="text-xs">
                        Submit
                      </Button>
                    )}
                    {canApproveOrReject && p.status === "submitted" && (
                      <>
                        <Button onClick={() => updateMutation.mutate({ id: p.proposal_id, data: { status: "approved" } })} variant="default" size="sm" className="text-xs flex items-center gap-1">
                          <Check size={12} /> Approve
                        </Button>
                        <Button onClick={() => updateMutation.mutate({ id: p.proposal_id, data: { status: "rejected" } })} variant="outline" size="sm" className="text-xs flex items-center gap-1">
                          <X size={12} /> Reject
                        </Button>
                      </>
                    )}
                    {canPublish && p.status === "approved" && (
                      <Button onClick={() => applyMutation.mutate(p.proposal_id)} variant="default" size="sm" className="text-xs flex items-center gap-1">
                        <ArrowUpRight size={12} /> Apply to New Version
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default DocumentProposals;
