import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { ChangeRequest, ReviewComment } from "../types";
import { FileText, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { useAuth } from "../auth/AuthContext";

export function ChangeRequests() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("change_request:create");
  const canReview = hasPermission("change_request:review");
  const canApprove = hasPermission("change_request:approve");
  const [statusFilter, setStatusFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [viewingCr, setViewingCr] = useState<ChangeRequest | null>(null);
  const [form, setForm] = useState({
    document_id: "",
    version_id: "",
    title: "",
    description: "",
    change_type: "minor",
  });
  const [commentForm, setCommentForm] = useState("");

  // The register is restricted to reviewers; do not fire a request that would 403.
  const { data: crs = [], isLoading } = useQuery({
    queryKey: ["change-requests", statusFilter],
    queryFn: () => safetyApi.listChangeRequests({ status: statusFilter || undefined }),
    enabled: canReview,
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createChangeRequest(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["change-requests"] });
      setIsCreating(false);
      setForm({ document_id: "", version_id: "", title: "", description: "", change_type: "minor" });
    },
  });

  const submitMutation = useMutation({
    mutationFn: (id: string) => safetyApi.submitChangeRequest(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["change-requests"] });
      if (viewingCr) setViewingCr({ ...viewingCr, status: "submitted" });
    },
  });

  const reviewMutation = useMutation({
    mutationFn: (id: string) => safetyApi.reviewChangeRequest(id, {}),
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ["change-requests"] });
      if (viewingCr) setViewingCr({ ...viewingCr, status: data.status, reviewer_id: data.reviewer_id });
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => safetyApi.approveChangeRequest(id, {}),
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ["change-requests"] });
      if (viewingCr) setViewingCr({ ...viewingCr, status: data.status, approver_id: data.approver_id });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      safetyApi.rejectChangeRequest(id, { rejection_reason: reason }),
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ["change-requests"] });
      if (viewingCr) setViewingCr({ ...viewingCr, status: data.status, rejection_reason: data.rejection_reason });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => safetyApi.deleteChangeRequest(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["change-requests"] });
      setViewingCr(null);
    },
  });

  const { data: comments = [] } = useQuery({
    queryKey: ["review-comments", viewingCr?.cr_id],
    queryFn: () =>
      viewingCr?.cr_id ? safetyApi.listReviewComments(viewingCr.cr_id).then((r) => r) : [],
    enabled: !!viewingCr?.cr_id,
  });

  const addCommentMutation = useMutation({
    mutationFn: (content: string) =>
      viewingCr?.cr_id ? safetyApi.addReviewComment(viewingCr.cr_id, { content }).then((r) => r) : Promise.reject(),
    onSuccess: () => {
      setCommentForm("");
      if (viewingCr?.cr_id) {
        safetyApi.listReviewComments(viewingCr.cr_id).then((r) => qc.setQueryData(["review-comments", viewingCr.cr_id], r));
      }
    },
  });

  const stats = {
    total: crs.length,
    open: crs.filter((c: ChangeRequest) => c.status === "open").length,
    submitted: crs.filter((c: ChangeRequest) => c.status === "submitted").length,
    under_review: crs.filter((c: ChangeRequest) => c.status === "under_review").length,
    approved: crs.filter((c: ChangeRequest) => c.status === "approved").length,
    rejected: crs.filter((c: ChangeRequest) => c.status === "rejected").length,
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">Change Requests</h1>
          <p className="app-subtitle">Propose, review, approve, and track controlled document changes.</p>
        </div>
        {canCreate && (
          <Button onClick={() => setIsCreating(true)} variant="default" size="sm">
            <Plus size={16} /> New Change Request
          </Button>
        )}
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="app-surface p-4">
          <div className="app-label">Total</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.total}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.open}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Submitted</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.submitted}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Under Review</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.under_review}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Approved</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.approved}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Rejected</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.rejected}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Change Requests</div>
          <div className="flex gap-2">
            <Select onValueChange={(e) => setStatusFilter(e)}>
              <SelectTrigger id="cr_status_filter" name="status" aria-label="Filter by status">
                <SelectValue placeholder={statusFilter || "All statuses"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All statuses</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="submitted">Submitted</SelectItem>
                <SelectItem value="under_review">Under Review</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {!canReview ? (
          <div className="p-10 text-center">
            <p className="text-sm font-bold text-kfl-text">The change-request register is restricted.</p>
            <p className="mt-1 text-xs text-kfl-muted">
              Viewing it requires the review permission. You can still raise a change request.
            </p>
          </div>
        ) : isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading change requests…</div>
        ) : crs.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <FileText size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No change requests found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create a change request to propose a controlled document change.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Document</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Requester</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {crs.map((cr: ChangeRequest) => (
                  <tr key={cr.cr_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{cr.cr_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{cr.document_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary max-w-xs truncate">{cr.title}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{cr.change_type}</td>
                    <td className="px-4 py-4"><Badge variant={cr.status === "approved" ? "default" : cr.status === "submitted" || cr.status === "under_review" ? "secondary" : cr.status === "rejected" ? "destructive" : "outline"} className={`badge ${cr.status === "approved" ? "bg-kfl-status-info-bg text-kfl-status-info" : cr.status === "submitted" || cr.status === "under_review" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : cr.status === "rejected" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{cr.status}</Badge></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{cr.requester_id}</td>
                    <td className="px-4 py-4 text-right">
                      <Button variant="outline" size="sm" onClick={() => setViewingCr(cr)}>
                        View
                      </Button>
                      {canCreate && cr.status === "open" && (
                        <>
                          <Button variant="outline" size="sm" onClick={() => {
                            setForm({
                              document_id: cr.document_id,
                              version_id: cr.version_id || "",
                              title: cr.title,
                              description: cr.description,
                              change_type: cr.change_type,
                            });
                            setIsCreating(true);
                            setViewingCr(null);
                          }}>
                            Edit
                          </Button>
                          <Button variant="destructive" size="sm" aria-label={`Delete change request ${cr.cr_id}`} onClick={() => {
                            if (confirm("Delete this change request?")) deleteMutation.mutate(cr.cr_id);
                          }}>
                            <Trash2 size={14} />
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {(isCreating || viewingCr) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="app-surface w-full max-w-2xl">
            {viewingCr && !isCreating ? (
              <>
              <div className="border-b border-kfl-border px-5 py-4">
                <h2 className="app-modal-title">Change Request {viewingCr.cr_id}</h2>
                <p className="mt-1 text-xs text-kfl-muted">{viewingCr.title}</p>
              </div>
              <div className="space-y-4 px-5 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Document</label>
                    <p className="text-sm text-kfl-secondary">{viewingCr.document_id}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Version</label>
                    <p className="text-sm text-kfl-secondary">{viewingCr.version_id || "—"}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Type</label>
                    <p className="text-sm text-kfl-secondary">{viewingCr.change_type}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Status</label>
                    <Badge variant={viewingCr.status === "approved" ? "default" : viewingCr.status === "submitted" || viewingCr.status === "under_review" ? "secondary" : viewingCr.status === "rejected" ? "destructive" : "outline"} className={`badge ${viewingCr.status === "approved" ? "bg-kfl-status-info-bg text-kfl-status-info" : viewingCr.status === "submitted" || viewingCr.status === "under_review" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : viewingCr.status === "rejected" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{viewingCr.status}</Badge>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Requester</label>
                    <p className="text-sm text-kfl-secondary">{viewingCr.requester_id}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Reviewer</label>
                    <p className="text-sm text-kfl-secondary">{viewingCr.reviewer_id || "—"}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Approver</label>
                    <p className="text-sm text-kfl-secondary">{viewingCr.approver_id || "—"}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Created</label>
                    <p className="text-sm text-kfl-secondary">{viewingCr.created_at}</p>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-kfl-muted">Description</label>
                  <p className="mt-1 text-sm text-kfl-secondary whitespace-pre-wrap">{viewingCr.description}</p>
                </div>
                {viewingCr.rejection_reason && (
                  <div className="p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger">
                    <label className="block text-xs font-semibold text-kfl-status-danger">Rejection Reason</label>
                    <p className="mt-1 text-sm text-kfl-status-danger">{viewingCr.rejection_reason}</p>
                  </div>
                )}
                <div className="border-t border-kfl-border pt-4">
                  <label className="block text-xs font-semibold text-kfl-muted">Review Comments</label>
                  <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                    {comments.length === 0 ? (
                      <p className="text-xs text-kfl-muted">No comments yet.</p>
                    ) : (
                      comments.map((c: ReviewComment) => (
                        <div key={c.comment_id} className="p-2 border-b border-kfl-border text-sm">
                          <p className="text-kfl-secondary">{c.content}</p>
                          <p className="text-[10px] text-kfl-muted">{c.author_id} · {c.created_at}</p>
                        </div>
                      ))
                    )}
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Textarea
                      id="cr_comment"
                      name="content"
                      className="flex-1 min-h-[80px]"
                      placeholder="Add a review comment…"
                      value={commentForm}
                      onChange={(e) => setCommentForm(e.target.value)}
                    />
                    <Button
                      id="cr_add_comment"
                      variant="default"
                      size="sm"
                      disabled={!commentForm.trim()}
                      onClick={() => addCommentMutation.mutate(commentForm.trim())}
                    >
                      Add
                    </Button>
                  </div>
                </div>
                <div className="flex justify-end gap-2 border-t border-kfl-border pt-4">
                  <Button variant="outline" size="sm" onClick={() => setViewingCr(null)}>
                    Close
                  </Button>
                  {canCreate && viewingCr.status === "open" && (
                    <Button
                      id="cr_submit"
                      variant="default"
                      size="sm"
                      disabled={submitMutation.isPending}
                      onClick={() => submitMutation.mutate(viewingCr.cr_id)}
                    >
                      {submitMutation.isPending ? "Submitting…" : "Submit for Review"}
                    </Button>
                  )}
                  {canReview && viewingCr.status === "submitted" && (
                    <>
                      <Button
                        id="cr_review"
                        variant="default"
                        size="sm"
                        disabled={reviewMutation.isPending}
                        onClick={() => reviewMutation.mutate(viewingCr.cr_id)}
                      >
                        {reviewMutation.isPending ? "Reviewing…" : "Start Review"}
                      </Button>
                    </>
                  )}
                  {canApprove && viewingCr.status === "under_review" && (
                    <>
                      <Button
                        id="cr_approve"
                        variant="default"
                        size="sm"
                        disabled={approveMutation.isPending}
                        onClick={() => approveMutation.mutate(viewingCr.cr_id)}
                      >
                        {approveMutation.isPending ? "Approving…" : "Approve"}
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => {
                        const reason = prompt("Rejection reason:");
                        if (reason !== null) rejectMutation.mutate({ id: viewingCr!.cr_id, reason });
                      }}>
                        Reject
                      </Button>
                    </>
                  )}
                </div>
              </div>
              </>

            ) : (
              <>
              <div className="border-b border-kfl-border px-5 py-4">
                <h2 className="app-modal-title">{isCreating ? "New Change Request" : "Edit Change Request"}</h2>
                <p className="mt-1 text-xs text-kfl-muted">
                  {isCreating ? "Propose a new controlled document change." : "Update change request details."}
                </p>
              </div>
              <div className="space-y-3 px-5 py-4">
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Document ID</span>
                  <Input
                    id="cr_document_id"
                    name="document_id"
                    value={form.document_id}
                    onChange={(e) => setForm({ ...form, document_id: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Version ID</span>
                  <Input
                    id="cr_version_id"
                    name="version_id"
                    value={form.version_id}
                    onChange={(e) => setForm({ ...form, version_id: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Title</span>
                  <Input
                    id="cr_title"
                    name="title"
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Description</span>
                  <Textarea
                    id="cr_description"
                    name="description"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Change Type</span>
                  <Select onValueChange={(e) => setForm({ ...form, change_type: e })}>
                    <SelectTrigger id="cr_change_type" name="change_type">
                      <SelectValue placeholder={form.change_type} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="minor">Minor</SelectItem>
                      <SelectItem value="major">Major</SelectItem>
                      <SelectItem value="emergency">Emergency</SelectItem>
                    </SelectContent>
                  </Select>
                </label>
              </div>
              <div className="flex justify-end gap-2 border-t border-kfl-border px-5 py-4">
                <Button variant="outline" size="sm" onClick={() => { setIsCreating(false); setViewingCr(null); }}>
                  Cancel
                </Button>
                <Button
                  id="cr_create_submit"
                  variant="default"
                  size="sm"
                  disabled={!form.document_id || !form.title || !form.description || createMutation.isPending}
                  onClick={() => createMutation.mutate(form)}
                >
                  {createMutation.isPending ? "Creating…" : "Create"}
                </Button>
              </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
