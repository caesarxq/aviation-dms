import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { ChangeRequest, ReviewComment } from "../types";
import { FileText, Plus, Trash2 } from "lucide-react";

function statusClass(status: string) {
  switch (status.toLowerCase()) {
    case "approved": return "app-status app-status-healthy";
    case "submitted": return "app-status app-status-warning";
    case "under_review": return "app-status app-status-info";
    case "rejected": return "app-status app-status-critical";
    case "open": return "app-status app-status-info";
    default: return "app-status app-status-muted";
  }
}

export function ChangeRequests() {
  const qc = useQueryClient();
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

  const { data: crs = [], isLoading } = useQuery({
    queryKey: ["change-requests", statusFilter],
    queryFn: () => safetyApi.listChangeRequests({ status: statusFilter || undefined }),
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
        <button className="app-btn" onClick={() => setIsCreating(true)}>
          <Plus size={16} /> New Change Request
        </button>
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
            <select
              id="cr_status_filter"
              name="status"
              aria-label="Filter by status"
              className="app-input w-full md:w-auto"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="submitted">Submitted</option>
              <option value="under_review">Under Review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {isLoading ? (
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
                    <td className="px-4 py-4"><span className={statusClass(cr.status)}>{cr.status}</span></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{cr.requester_id}</td>
                    <td className="px-4 py-4 text-right">
                      <button
                        id={`view_cr_${cr.cr_id}`}
                        className="app-btn app-btn-ghost"
                        onClick={() => setViewingCr(cr)}
                      >
                        View
                      </button>
                      {cr.status === "open" && (
                        <>
                          <button
                            id={`edit_cr_${cr.cr_id}`}
                            className="app-btn app-btn-ghost"
                            onClick={() => {
                              setForm({
                                document_id: cr.document_id,
                                version_id: cr.version_id || "",
                                title: cr.title,
                                description: cr.description,
                                change_type: cr.change_type,
                              });
                              setIsCreating(true);
                              setViewingCr(null);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            id={`delete_cr_${cr.cr_id}`}
                            aria-label={`Delete change request ${cr.cr_id}`}
                            className="app-btn app-btn-ghost"
                            onClick={() => {
                              if (confirm("Delete this change request?")) deleteMutation.mutate(cr.cr_id);
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
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
                    <p className={`text-sm font-medium ${statusClass(viewingCr.status)}`}>{viewingCr.status}</p>
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
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded">
                    <label className="block text-xs font-semibold text-rose-700">Rejection Reason</label>
                    <p className="mt-1 text-sm text-rose-700">{viewingCr.rejection_reason}</p>
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
                    <textarea
                      id="cr_comment"
                      name="content"
                      className="app-input flex-1 min-h-[80px]"
                      placeholder="Add a review comment…"
                      value={commentForm}
                      onChange={(e) => setCommentForm(e.target.value)}
                    />
                    <button
                      id="cr_add_comment"
                      className="app-btn"
                      disabled={!commentForm.trim()}
                      onClick={() => addCommentMutation.mutate(commentForm.trim())}
                    >
                      Add
                    </button>
                  </div>
                </div>
                <div className="flex justify-end gap-2 border-t border-kfl-border pt-4">
                  <button className="app-btn app-btn-ghost" onClick={() => setViewingCr(null)}>
                    Close
                  </button>
                  {viewingCr.status === "open" && (
                    <button
                      id="cr_submit"
                      className="app-btn"
                      disabled={submitMutation.isPending}
                      onClick={() => submitMutation.mutate(viewingCr.cr_id)}
                    >
                      {submitMutation.isPending ? "Submitting…" : "Submit for Review"}
                    </button>
                  )}
                  {viewingCr.status === "submitted" && (
                    <>
                      <button
                        id="cr_review"
                        className="app-btn"
                        disabled={reviewMutation.isPending}
                        onClick={() => reviewMutation.mutate(viewingCr.cr_id)}
                      >
                        {reviewMutation.isPending ? "Reviewing…" : "Start Review"}
                      </button>
                    </>
                  )}
                  {viewingCr.status === "under_review" && (
                    <>
                      <button
                        id="cr_approve"
                        className="app-btn"
                        disabled={approveMutation.isPending}
                        onClick={() => approveMutation.mutate(viewingCr.cr_id)}
                      >
                        {approveMutation.isPending ? "Approving…" : "Approve"}
                      </button>
                      <button
                        id="cr_reject"
                        className="app-btn app-btn-ghost"
                        onClick={() => {
                          const reason = prompt("Rejection reason:");
                          if (reason !== null) rejectMutation.mutate({ id: viewingCr!.cr_id, reason });
                        }}
                      >
                        Reject
                      </button>
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
                  <input
                    id="cr_document_id"
                    name="document_id"
                    className="app-input"
                    value={form.document_id}
                    onChange={(e) => setForm({ ...form, document_id: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Version ID</span>
                  <input
                    id="cr_version_id"
                    name="version_id"
                    className="app-input"
                    value={form.version_id}
                    onChange={(e) => setForm({ ...form, version_id: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Title</span>
                  <input
                    id="cr_title"
                    name="title"
                    className="app-input"
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Description</span>
                  <textarea
                    id="cr_description"
                    name="description"
                    className="app-input"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </label>
                <label className="block text-sm text-kfl-secondary">
                  <span className="mb-1 block text-xs font-semibold text-kfl-muted">Change Type</span>
                  <select
                    id="cr_change_type"
                    name="change_type"
                    className="app-input"
                    value={form.change_type}
                    onChange={(e) => setForm({ ...form, change_type: e.target.value })}
                  >
                    <option value="minor">Minor</option>
                    <option value="major">Major</option>
                    <option value="emergency">Emergency</option>
                  </select>
                </label>
              </div>
              <div className="flex justify-end gap-2 border-t border-kfl-border px-5 py-4">
                <button className="app-btn app-btn-ghost" onClick={() => { setIsCreating(false); setViewingCr(null); }}>
                  Cancel
                </button>
                <button
                  id="cr_create_submit"
                  className="app-btn"
                  disabled={!form.document_id || !form.title || !form.description || createMutation.isPending}
                  onClick={() => createMutation.mutate(form)}
                >
                  {createMutation.isPending ? "Creating…" : "Create"}
                </button>
              </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
