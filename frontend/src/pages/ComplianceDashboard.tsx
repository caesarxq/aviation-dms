import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import api from "../api/client";
import {
  controlledDocumentApi,
  ExtractionRequest,
} from "../api/controlledDocument";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/ui/Toast";

export function ComplianceDashboard() {
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const canApprove = hasPermission("document.extract.approve");
  const canReadAudit = hasPermission("audit:read");
  const qc = useQueryClient();

  const [approveReqId, setApproveReqId] = useState("");
  const [rejectReqId, setRejectReqId] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [showActionModal, setShowActionModal] = useState(false);
  const [modalType, setModalType] = useState<"approve" | "reject">("approve");
  const [selectedRequest, setSelectedRequest] = useState<ExtractionRequest | null>(null);

  const { data: extractionRequests = [], isLoading: reqLoading } = useQuery({
    queryKey: ["extraction-requests"],
    queryFn: () => controlledDocumentApi.listExtractionRequests(),
    enabled: hasPermission("document.section.extract"),
  });

  const { data: auditEvents = [], isLoading: auditLoading } = useQuery({
    queryKey: ["audit-events"],
    queryFn: () => api.get("/p0/audit-events").then((r: any) => r.data),
    enabled: canReadAudit,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      controlledDocumentApi.approveExtractionRequest(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["extraction-requests"] });
      setShowActionModal(false);
      setReviewComment("");
      toast({ title: "Extraction request approved", type: "success" });
    },
    onError: (err: any) => {
      toast({ title: err.response?.data?.detail?.message || "Approval failed", type: "error" });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      controlledDocumentApi.rejectExtractionRequest(id).then(() => ({ id, comment })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["extraction-requests"] });
      setShowActionModal(false);
      setReviewComment("");
      toast({ title: "Extraction request rejected", type: "success" });
    },
    onError: (err: any) => {
      toast({ title: err.response?.data?.detail?.message || "Rejection failed", type: "error" });
    },
  });

  const handleApprove = (req: ExtractionRequest) => {
    setSelectedRequest(req);
    setApproveReqId(req.id);
    setModalType("approve");
    setShowActionModal(true);
  };

  const handleReject = (req: ExtractionRequest) => {
    setSelectedRequest(req);
    setRejectReqId(req.id);
    setModalType("reject");
    setShowActionModal(true);
  };

  const handleSubmitAction = () => {
    if (modalType === "approve" && approveReqId) {
      approveMutation.mutate(approveReqId);
    } else if (modalType === "reject" && rejectReqId) {
      rejectMutation.mutate({ id: rejectReqId, comment: reviewComment });
    }
  };

  const pending = extractionRequests.filter((r) => r.status === "pending");
  const approved = extractionRequests.filter((r) => r.status === "approved");
  const rejected = extractionRequests.filter((r) => r.status === "rejected");
  const expired = extractionRequests.filter((r) => r.status === "expired");

  const recentAudit = useMemo(
    () => auditEvents.slice(0, 10),
    [auditEvents]
  );

  if (!hasPermission("document.section.extract") && !canReadAudit) {
    return (
      <div className="p-6">
        <AlertCircle className="w-12 h-12 text-orange-500" />
        <h2 className="text-xl font-semibold mt-2">Access Restricted</h2>
        <p className="text-muted-foreground">
          You do not have permission to view compliance data.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Compliance Dashboard</h1>
          <p className="text-muted-foreground">
            Monitor extraction requests, audit events, and document compliance.
          </p>
        </div>
        {(reqLoading || auditLoading) && (
          <Loader2 className="w-6 h-6 animate-spin" />
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-amber-500" />
            <div>
              <div className="text-2xl font-bold">{pending.length}</div>
              <div className="text-xs text-muted-foreground">Pending Requests</div>
            </div>
          </div>
        </div>
        <div className="bg-card p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <div>
              <div className="text-2xl font-bold">{approved.length}</div>
              <div className="text-xs text-muted-foreground">Approved</div>
            </div>
          </div>
        </div>
        <div className="bg-card p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-500" />
            <div>
              <div className="text-2xl font-bold">{rejected.length}</div>
              <div className="text-xs text-muted-foreground">Rejected</div>
            </div>
          </div>
        </div>
        <div className="bg-card p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-500" />
            <div>
              <div className="text-2xl font-bold">{expired.length}</div>
              <div className="text-xs text-muted-foreground">Expired</div>
            </div>
          </div>
        </div>
      </div>

      {/* Extraction Requests Table */}
      <div className="bg-card p-6 rounded-xl border">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Extraction Requests</h3>
          <span className={`text-xs font-medium px-2 py-1 rounded ${
            pending.length > 0 ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"
          }`}>
            {pending.length} pending
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b">
                <th className="py-2 font-medium">Request ID</th>
                <th className="py-2 font-medium">Document</th>
                <th className="py-2 font-medium">Section</th>
                <th className="py-2 font-medium">Requested By</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Created</th>
                {canApprove ? (
                  <th className="py-2 font-medium text-center">Actions</th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {extractionRequests.map((req) => {
                const statusColor: Record<string, string> = {
                  pending: "bg-amber-100 text-amber-700",
                  approved: "bg-green-100 text-green-700",
                  rejected: "bg-red-100 text-red-700",
                  expired: "bg-gray-100 text-gray-700",
                  auto_approved: "bg-blue-100 text-blue-700",
                };
                return (
                  <tr key={req.id} className="border-b hover:bg-muted/50">
                    <td className="py-3 font-mono text-sm">{req.id}</td>
                    <td className="py-3">{req.document_id}</td>
                    <td className="py-3">{req.section_id || "—"}</td>
                    <td className="py-3">{req.requested_by}</td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${statusColor[req.status] || "bg-muted"}`}>
                        {req.status}
                      </span>
                    </td>
                    <td className="py-3 text-sm">{req.created_at}</td>
                    {canApprove && req.status === "pending" ? (
                      <td className="py-3 text-center">
                        <button
                          onClick={() => handleApprove(req)}
                          className="text-xs bg-green-500 text-white px-2 py-1 rounded hover:bg-green-600 disabled:opacity-50"
                          disabled={approveMutation.isPending || rejectMutation.isPending}
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleReject(req)}
                          className="ml-1 text-xs bg-red-500 text-white px-2 py-1 rounded hover:bg-red-600 disabled:opacity-50"
                          disabled={approveMutation.isPending || rejectMutation.isPending}
                        >
                          Reject
                        </button>
                      </td>
                    ) : (
                      <td className="py-3 text-center">
                        {req.reviewed_by && (
                          <span className="text-xs text-muted-foreground">
                            Reviewed by {req.reviewed_by}
                          </span>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
              {extractionRequests.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-4 text-muted-foreground text-center">
                    No extraction requests found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Audit Events */}
      {canReadAudit && (
        <div className="bg-card p-6 rounded-xl border">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Recent Audit Events</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 font-medium">Time</th>
                  <th className="py-2 font-medium">Actor</th>
                  <th className="py-2 font-medium">Action</th>
                  <th className="py-2 font-medium">Entity</th>
                  <th className="py-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {recentAudit.map((event: any) => (
                  <tr key={event.event_id} className="border-b">
                    <td className="py-3 font-mono text-xs">{event.timestamp}</td>
                    <td className="py-3">{event.actor_id}</td>
                    <td className="py-3">{event.action}</td>
                    <td className="py-3">{event.entity_type}:{event.entity_id}</td>
                    <td className="py-3 text-muted-foreground">
                      {event.details ? JSON.stringify(event.details).slice(0, 80) : ""}
                    </td>
                  </tr>
                ))}
                {recentAudit.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-4 text-muted-foreground text-center">
                      No audit events found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Rejection Comment Modal */}
      {modalType === "reject" && showActionModal && selectedRequest && (
        <Modal
          open={showActionModal}
          onClose={() => setShowActionModal(false)}
          title="Reject Extraction Request"
          description={`Request ${selectedRequest.id} for document ${selectedRequest.document_id}`}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Rejection Reason</label>
              <textarea
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                placeholder="Explain why this extraction request is being rejected..."
                className="w-full px-3 py-2 border rounded h-32"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowActionModal(false)}
                className="px-4 py-2 text-muted-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitAction}
                disabled={rejectMutation.isPending || !reviewComment.trim()}
                className="px-4 py-2 bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
              >
                {rejectMutation.isPending ? "Rejecting..." : "Reject Request"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default ComplianceDashboard;
