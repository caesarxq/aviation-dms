import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { listDocuments } from "../api/documents";
import {
  controlledDocumentApi,
  DocumentClassification,
  DocumentPermissionGrant,
} from "../api/controlledDocument";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/ui/Toast";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

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

function classificationBadge(code: string) {
  const variant = code === "KCAA_APPROVED" ? "destructive" : code === "CONTROLLED" ? "secondary" : "default";
  const bg = code === "KCAA_APPROVED" ? "bg-kfl-status-danger-bg" : code === "CONTROLLED" ? "bg-kfl-status-warning-bg" : "bg-kfl-status-info-bg";
  const fg = code === "KCAA_APPROVED" ? "text-kfl-status-danger" : code === "CONTROLLED" ? "text-kfl-status-warning" : "text-kfl-status-info";
  return <Badge variant={variant} className={`badge ${bg} ${fg}`}>{code}</Badge>;
}

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

  const { data: documentPage, isLoading: docsLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => listDocuments(),
    enabled: canManage,
  });
  const docs = documentPage?.data ?? [];

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
        <ShieldAlert className="w-12 h-12 text-kfl-status-warning" />
        <h2 className="text-xl font-semibold mt-2 text-kfl-text">Access Restricted</h2>
        <p className="text-kfl-muted">
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
          <h1 className="text-2xl font-bold text-kfl-text">Document Controller</h1>
          <p className="text-kfl-muted">
            Manage document classifications, section boundaries, and role-based permissions.
          </p>
        </div>
        {docsLoading ? (
          <Loader2 className="w-6 h-6 animate-spin text-kfl-muted" />
        ) : null}
      </div>

      {/* Extraction Requests Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="app-surface p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-kfl-status-warning" />
            <div>
              <div className="text-2xl font-bold text-kfl-text">{pendingRequests.length}</div>
              <div className="text-xs text-kfl-muted">Pending Extraction Requests</div>
            </div>
          </div>
        </div>
        <div className="app-surface p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-kfl-status-info" />
            <div>
              <div className="text-2xl font-bold text-kfl-text">{approvedRequests.length}</div>
              <div className="text-xs text-kfl-muted">Approved Extractions</div>
            </div>
          </div>
        </div>
        <div className="app-surface p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <XCircle className="w-5 h-5 text-kfl-status-danger" />
            <div>
              <div className="text-2xl font-bold text-kfl-text">{rejectedRequests.length}</div>
              <div className="text-xs text-kfl-muted">Rejected Requests</div>
            </div>
          </div>
        </div>
      </div>

      {/* Documents Table */}
      <div className="app-surface p-6 rounded-xl border">
        <h3 className="font-semibold mb-4 text-kfl-text">Documents</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-kfl-border">
                <th className="py-2 font-medium text-kfl-text">Document ID</th>
                <th className="py-2 font-medium text-kfl-text">Title</th>
                <th className="py-2 font-medium text-kfl-text">Classification</th>
                <th className="py-2 font-medium text-kfl-text">KCAA Required</th>
                <th className="py-2 font-medium text-kfl-text">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc: any) => (
                <tr key={doc.document_id} className="border-b border-kfl-border hover:bg-kfl-surface-subtle">
                  <td className="py-3 font-mono text-sm text-kfl-text">{doc.document_id}</td>
                  <td className="py-3 text-kfl-text">{doc.title}</td>
                  <td className="py-3">{classificationBadge(doc.classification)}</td>
                  <td className="py-3">
                    {doc.kcaa_approval_required ? (
                      <Badge variant="destructive" className="badge text-xs">Yes</Badge>
                    ) : (
                      <Badge variant="outline" className="badge text-xs">No</Badge>
                    )}
                  </td>
                  <td className="py-3">
                    <Button
                      onClick={() => {
                        setClassifyDocId(doc.document_id);
                        setClassifyCode(doc.classification || "");
                        setShowClassifyModal(true);
                      }}
                      variant="link"
                      size="sm"
                    >
                      Classify
                    </Button>
                    <Button
                      onClick={() => {
                        setPermDocId(doc.document_id);
                        setPermGrants([]);
                        setShowPermModal(true);
                      }}
                      variant="link"
                      size="sm"
                      className="ml-2"
                    >
                      Permissions
                    </Button>
                  </td>
                </tr>
              ))}
              {docs.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-kfl-muted">
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
        <div className="app-surface p-6 rounded-xl border">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-kfl-text">Pending Extraction Approvals</h3>
            <Badge variant="destructive" className="badge text-xs">
              Requires review
            </Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-kfl-border">
                  <th className="py-2 font-medium text-kfl-text">Request ID</th>
                  <th className="py-2 font-medium text-kfl-text">Document</th>
                  <th className="py-2 font-medium text-kfl-text">Section</th>
                  <th className="py-2 font-medium text-kfl-text">Requested By</th>
                  <th className="py-2 font-medium text-kfl-text">Reason</th>
                  <th className="py-2 font-medium text-kfl-text">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingRequests.map((req) => (
                  <tr key={req.id} className="border-b border-kfl-border hover:bg-kfl-surface-subtle">
                    <td className="py-3 font-mono text-sm text-kfl-text">{req.id}</td>
                    <td className="py-3 text-kfl-text">{req.document_id}</td>
                    <td className="py-3 text-kfl-text">{req.section_id || "—"}</td>
                    <td className="py-3 text-kfl-text">{req.requested_by}</td>
                    <td className="py-3 text-kfl-text">{req.reason}</td>
                    <td className="py-3">
                      <Button
                        onClick={() => {
                          toast({ title: "Approval requires document.extract.approve permission", type: "warning" });
                        }}
                        variant="outline"
                        size="sm"
                        disabled={!hasPermission("document.extract.approve")}
                      >
                        Approve/Reject
                      </Button>
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
            <label className="block text-sm font-medium mb-2 text-kfl-text">Document</label>
            <p className="text-kfl-muted text-sm">{classifyDocId}</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2 text-kfl-text">Classification</label>
            <Select onValueChange={(e) => setClassifyCode(e)}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={classifyCode} />
              </SelectTrigger>
              <SelectContent>
                {classifications.map((c) => (
                  <SelectItem key={c.code} value={c.code}>
                    {c.code} - {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowClassifyModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleClassify}
              disabled={classifyMutation.isPending}
              variant="default"
              size="sm"
            >
              {classifyMutation.isPending ? "Classifying…" : "Save Classification"}
            </Button>
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
                <tr className="border-b border-kfl-border">
                  <th className="py-2 font-medium text-kfl-text">Role</th>
                  {PERMISSIONS.map((p) => (
                    <th key={p.code} className="py-2 font-medium text-center w-12 text-kfl-muted">
                      <span className="text-xs opacity-60">{p.code.replace("document:", "").replace("document.section.", "s.")}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROLES.map((role) => (
                  <tr key={role} className="border-b border-kfl-border hover:bg-kfl-surface-subtle">
                    <td className="py-3 font-mono text-sm text-kfl-text">{role}</td>
                    {PERMISSIONS.map((perm) => (
                      <td key={perm.code} className="py-3 text-center">
                        <Button
                          variant={isPermGranted(role, perm.code) ? "default" : "outline"}
                          size="sm"
                          className="h-8 w-8 rounded-full p-0"
                          onClick={() => togglePermission(role, perm.code)}
                        >
                          {isPermGranted(role, perm.code) && <CheckCircle className="w-4 h-4" />}
                        </Button>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-xs text-kfl-muted">
            Click cells to toggle permissions. Changes apply immediately on save.
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowPermModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSavePermissions}
              disabled={permMutation.isPending}
              variant="default"
              size="sm"
            >
              {permMutation.isPending ? "Saving…" : "Save Permissions"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default DocumentControllerDashboard;
