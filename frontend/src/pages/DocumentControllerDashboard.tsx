import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
} from "lucide-react";
import api from "../api/client";
import {
  controlledDocumentApi,
  DocumentClassification,
  DocumentPermissionGrant,
} from "../api/controlledDocument";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/ui/Toast";

const CLASSIFICATIONS: DocumentClassification[] = [
  {
    code: "PUBLIC",
    name: "Public Document",
    requires_watermark: true,
    allow_full_download: true,
    requires_approval: false,
  },
  {
    code: "TEMPLATE",
    name: "Template Document",
    requires_watermark: true,
    allow_full_download: true,
    requires_approval: false,
  },
  {
    code: "CONTROLLED",
    name: "Controlled Document",
    requires_watermark: true,
    allow_full_download: false,
    requires_approval: false,
  },
  {
    code: "KCAA_APPROVED",
    name: "KCAA-Approved Manual",
    requires_watermark: true,
    allow_full_download: false,
    requires_approval: true,
  },
];

const PERMISSIONS = [
  { code: "document:read", label: "View document" },
  { code: "document:download", label: "Download document" },
  { code: "document.section.view", label: "View sections" },
  { code: "document.section.extract", label: "Extract sections" },
  { code: "document.section.manage", label: "Manage sections" },
  { code: "document.policy.manage", label: "Manage policy" },
];

const ROLES = [
  "system_admin",
  "accountable_manager",
  "librarian",
  "head_quality",
  "head_safety",
  "head_security",
  "head_operations",
  "chief_pilot",
  "flight_ops_officer",
  "head_training",
  "head_maintenance",
  "dg_coordinator",
  "occurrence_reporter",
  "records_custodian",
  "independent_auditor",
  "as_contracted",
];

export function DocumentControllerDashboard() {
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const canManage = hasPermission("document.policy.manage");
  const qc = useQueryClient();

  const [classifyDocId, setClassifyDocId] = useState("");
  const [classifyCode, setClassifyCode] = useState("");
  const [showClassifyModal, setShowClassifyModal] = useState(false);
  const [permDocId, setPermDocId] = useState("");
  const [showPermModal, setShowPermModal] = useState(false);
  const [permGrants, setPermGrants] = useState<DocumentPermissionGrant[]>([]);

  const { data: docs = [], isLoading: docsLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
    enabled: canManage,
  });

  const { data: classifications = CLASSIFICATIONS } = useQuery({
    queryKey: ["document-classifications"],
    queryFn: () =>
      controlledDocumentApi.listDocumentClassifications().catch(() => CLASSIFICATIONS),
    enabled: canManage,
  });

  const { data: extractionRequests = [] as any[] } = useQuery({
    queryKey: ["extraction-requests"],
    queryFn: () => controlledDocumentApi.listExtractionRequests(),
    enabled: hasPermission("document.section.extract"),
  });

  const classifyMutation = useMutation({
    mutationFn: ({ docId, code }: { docId: string; code: string }) =>
      controlledDocumentApi.classifyDocument(docId, { classification_code: code }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      setShowClassifyModal(false);
      setClassifyDocId("");
      setClassifyCode("");
      toast({ title: "Document classified successfully", type: "success" });
    },
    onError: (err: any) => {
      toast({ title: err.response?.data?.detail?.message || "Classification failed", type: "error" });
    },
  });

  const permMutation = useMutation({
    mutationFn: (grants: DocumentPermissionGrant[]) =>
      controlledDocumentApi.setDocumentPermissions(permDocId, grants),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      setShowPermModal(false);
      setPermGrants([]);
      toast({ title: "Document permissions updated successfully", type: "success" });
    },
    onError: (err: any) => {
      toast({ title: err.response?.data?.detail?.message || "Permission update failed", type: "error" });
    },
  });

  const handleClassify = () => {
    if (!classifyDocId || !classifyCode) return;
    classifyMutation.mutate({ docId: classifyDocId, code: classifyCode });
  };

  const handleSavePermissions = () => {
    if (!permDocId || permGrants.length === 0) return;
    permMutation.mutate(permGrants);
  };

  const togglePermission = (roleId: string, permCode: string) => {
    setPermGrants((prev) => {
      const exists = prev.find((g) => g.role_id === roleId && g.permission_code === permCode);
      if (exists) {
        return prev.filter((g) => !(g.role_id === roleId && g.permission_code === permCode));
      }
      return [...prev, { role_id: roleId, permission_code: permCode, scope_section_id: null, valid_from: new Date().toISOString() }];
    });
  };

  const isPermGranted = (roleId: string, permCode: string) =>
    permGrants.some((g) => g.role_id === roleId && g.permission_code === permCode);

  const pendingRequests = extractionRequests.filter((r) => r.status === "pending");
  const approvedRequests = extractionRequests.filter((r) => r.status === "approved");
  const rejectedRequests = extractionRequests.filter((r) => r.status === "rejected");

  if (!canManage) {
    return (
      <div className="p-6">
        <ShieldAlert className="w-12 h-12 text-orange-500" />
        <h2 className="text-xl font-semibold mt-2">Access Restricted</h2>
        <p className="text-muted-foreground">
          You do not have permission to manage document classifications and permissions.
          Contact your document controller or system administrator.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Document Controller</h1>
          <p className="text-muted-foreground">
            Manage document classifications, section boundaries, and role-based permissions.
          </p>
        </div>
        {docsLoading ? (
          <Loader2 className="w-6 h-6 animate-spin" />
        ) : null}
      </div>

      {/* Extraction Requests Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-amber-500" />
            <div>
              <div className="text-2xl font-bold">{pendingRequests.length}</div>
              <div className="text-xs text-muted-foreground">Pending Extraction Requests</div>
            </div>
          </div>
        </div>
        <div className="bg-card p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <div>
              <div className="text-2xl font-bold">{approvedRequests.length}</div>
              <div className="text-xs text-muted-foreground">Approved Extractions</div>
            </div>
          </div>
        </div>
        <div className="bg-card p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-500" />
            <div>
              <div className="text-2xl font-bold">{rejectedRequests.length}</div>
              <div className="text-xs text-muted-foreground">Rejected Requests</div>
            </div>
          </div>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-card p-6 rounded-xl border">
        <h3 className="font-semibold mb-4">Documents</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b">
                <th className="py-2 font-medium">Document ID</th>
                <th className="py-2 font-medium">Title</th>
                <th className="py-2 font-medium">Classification</th>
                <th className="py-2 font-medium">KCAA Required</th>
                <th className="py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc: any) => (
                <tr key={doc.document_id} className="border-b hover:bg-muted/50">
                  <td className="py-3 font-mono text-sm">{doc.document_id}</td>
                  <td className="py-3">{doc.title}</td>
                  <td className="py-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      doc.classification === "KCAA_APPROVED"
                        ? "bg-amber-100 text-amber-800"
                        : doc.classification === "CONTROLLED"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-green-100 text-green-800"
                    }`}>
                      {doc.classification}
                    </span>
                  </td>
                  <td className="py-3">
                    {doc.kcaa_approval_required ? (
                      <span className="text-xs font-medium text-amber-600">Yes</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">No</span>
                    )}
                  </td>
                  <td className="py-3">
                    <button
                      onClick={() => {
                        setClassifyDocId(doc.document_id);
                        setClassifyCode(doc.classification || "");
                        setShowClassifyModal(true);
                      }}
                      className="text-sm text-primary hover:underline"
                    >
                      Classify
                    </button>
                    <button
                      onClick={() => {
                        setPermDocId(doc.document_id);
                        setPermGrants([]);
                        setShowPermModal(true);
                      }}
                      className="ml-2 text-sm text-primary hover:underline"
                    >
                      Permissions
                    </button>
                  </td>
                </tr>
              ))}
              {docs.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-muted-foreground text-center">
                    No documents found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pending Extraction Requests */}
      {pendingRequests.length > 0 && (
        <div className="bg-card p-6 rounded-xl border">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Pending Extraction Approvals</h3>
            <span className="text-xs font-medium bg-amber-100 text-amber-700 px-2 py-1 rounded">
              Requires review
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
                  <th className="py-2 font-medium">Reason</th>
                  <th className="py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingRequests.map((req) => (
                  <tr key={req.id} className="border-b hover:bg-muted/50">
                    <td className="py-3 font-mono text-sm">{req.id}</td>
                    <td className="py-3">{req.document_id}</td>
                    <td className="py-3">{req.section_id || "—"}</td>
                    <td className="py-3">{req.requested_by}</td>
                    <td className="py-3">{req.reason}</td>
                    <td className="py-3">
                      <button
                        onClick={() => {
                          toast({ title: "Approval requires document.extract.approve permission", type: "warning" });
                        }}
                        className="text-xs bg-amber-500 text-white px-2 py-1 rounded hover:bg-amber-600 disabled:opacity-50"
                        disabled={!hasPermission("document.extract.approve")}
                      >
                        Approve/Reject
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Classify Document Modal */}
      <Modal
        open={showClassifyModal}
        onClose={() => setShowClassifyModal(false)}
        title="Classify Document"
        description="Select the document classification. This determines download and extraction rules."
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Document</label>
            <p className="text-muted-foreground text-sm">{classifyDocId}</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Classification</label>
            <select
              value={classifyCode}
              onChange={(e) => setClassifyCode(e.target.value)}
              className="w-full px-3 py-2 border rounded"
            >
              {classifications.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.code} - {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowClassifyModal(false)}
              className="px-4 py-2 text-muted-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleClassify}
              disabled={classifyMutation.isPending}
              className="px-4 py-2 bg-primary text-white hover:bg-primary/90 disabled:opacity-50"
            >
              {classifyMutation.isPending ? "Classifying..." : "Save Classification"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Document Permissions Modal */}
      <Modal
        open={showPermModal}
        onClose={() => setShowPermModal(false)}
        title={`Document Permissions — ${permDocId}`}
        description="Grant role-based permissions for this document."
      >
        <div className="space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th className="py-2 font-medium">Role</th>
                  {PERMISSIONS.map((p) => (
                    <th key={p.code} className="py-2 font-medium text-center w-12">
                      <span className="text-xs opacity-60">{p.code.replace("document:", "").replace("document.section.", "s.")}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROLES.map((role) => (
                  <tr key={role} className="border-b hover:bg-muted/50">
                    <td className="py-3 font-mono text-sm">{role}</td>
                    {PERMISSIONS.map((perm) => (
                      <td key={perm.code} className="py-3 text-center">
                        <button
                          onClick={() => togglePermission(role, perm.code)}
                          className={`w-8 h-8 rounded-full ${
                            isPermGranted(role, perm.code)
                              ? "bg-primary text-white"
                              : "bg-muted border border-border"
                          }`}
                        >
                          {isPermGranted(role, perm.code) && (
                            <CheckCircle className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-xs text-muted-foreground">
            Click cells to toggle permissions. Changes apply immediately on save.
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowPermModal(false)}
              className="px-4 py-2 text-muted-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleSavePermissions}
              disabled={permMutation.isPending}
              className="px-4 py-2 bg-primary text-white hover:bg-primary/90 disabled:opacity-50"
            >
              {permMutation.isPending ? "Saving..." : "Save Permissions"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default DocumentControllerDashboard;
