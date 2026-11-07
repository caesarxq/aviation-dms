import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Upload, CheckCircle, Clock, AlertTriangle, Download } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useToast } from "../components/ui/Toast";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";

const DOCUMENT_TYPES = [
  "pilot_license", "medical", "type_rating", "proficiency_check",
  "dg_training", "security_training", "sms_awareness", "crm",
  "indoctrination", "background_check", "english_proficiency", "avsec",
];
const UPLOAD_HISTORY_PAGE_SIZE = 50;
const VERIFICATION_QUEUE_PAGE_SIZE = 50;

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function canReviewUpload(upload: any): boolean {
  return upload.can_review === true;
}

export function SelfServiceUpload() {
  const { toast } = useToast();
  const { profile, hasPermission } = useAuth();
  const qc = useQueryClient();
  const personId = profile?.user.user_id ?? "";
  const canManagePersonnel = hasPermission("personnel:manage");
  const canReadPersonnel = hasPermission("personnel:read") || canManagePersonnel;
  const [statusFilter, setStatusFilter] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [historyPage, setHistoryPage] = useState(0);
  const [queuePage, setQueuePage] = useState(0);
  const [uploadForm, setUploadForm] = useState({ license_type: "pilot_license", document_type: "license_copy" });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [rejectingUploadId, setRejectingUploadId] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");

  const { data: uploadsPageData = { items: [], hasNext: false }, isLoading, isError, error: loadError, refetch } = useQuery({
    queryKey: ["personnel-uploads", personId, statusFilter, historyPage],
    queryFn: async () => {
      const response = await api.get(`/p2/personnel/uploads/${encodeURIComponent(personId)}`, {
        params: {
          status: statusFilter || undefined,
          limit: UPLOAD_HISTORY_PAGE_SIZE + 1,
          offset: historyPage * UPLOAD_HISTORY_PAGE_SIZE,
        },
      });
      if (response.status !== 200) throw new Error("Unable to load personnel uploads");
      const records = response.data as any[];
      return {
        items: records.slice(0, UPLOAD_HISTORY_PAGE_SIZE),
        hasNext: records.length > UPLOAD_HISTORY_PAGE_SIZE,
      };
    },
    enabled: !!personId,
  });
  const uploads = uploadsPageData.items;

  const { data: queuePageData = { items: [], hasNext: false }, isLoading: queueLoading, isError: queueError, refetch: refetchQueue } = useQuery({
    queryKey: ["personnel-upload-verification-queue", queuePage],
    queryFn: async () => {
      const response = await api.get("/p2/personnel/uploads", {
        params: { status: "pending", limit: VERIFICATION_QUEUE_PAGE_SIZE + 1, offset: queuePage * VERIFICATION_QUEUE_PAGE_SIZE },
      });
      if (response.status !== 200) throw new Error("Unable to load the verification queue");
      const records = response.data as any[];
      return {
        items: records.slice(0, VERIFICATION_QUEUE_PAGE_SIZE),
        hasNext: records.length > VERIFICATION_QUEUE_PAGE_SIZE,
      };
    },
    enabled: canReadPersonnel,
  });
  const verificationQueue = queuePageData.items;

  const filteredUploads = uploads;

  useUnsavedChanges(showUpload && dirty);

  const createMutation = useMutation({
    mutationFn: (data: { license_type: string; document_type: string; file: File }) => {
      const formData = new FormData();
      formData.append("license_type", data.license_type);
      formData.append("document_type", data.document_type);
      formData.append("file", data.file);
      return api.post("/p2/personnel/uploads/file", formData).then((r: any) => {
        if (r.status !== 200) throw new Error("Upload was not accepted");
        return r.data;
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["personnel-uploads", personId] });
      qc.invalidateQueries({ queryKey: ["personnel-upload-verification-queue"] });
      setHistoryPage(0);
      setQueuePage(0);
      setShowUpload(false);
      setDirty(false);
      setUploadError("");
      setUploadForm({ license_type: "pilot_license", document_type: "license_copy" });
      setSelectedFile(null);
      toast({ title: "Credential uploaded", message: "Your document has been submitted for verification.", type: "success" });
    },
    onError: (error: unknown) => {
      setUploadError(getErrorMessage(error, "Failed to upload credential. Please try again."));
    },
  });

  const verifyMutation = useMutation({
    mutationFn: ({ id, status, reason }: { id: string; status: string; reason?: string }) =>
      api.patch(`/p2/personnel/uploads/${encodeURIComponent(id)}/verify`, { verification_status: status, rejection_reason: reason }).then((r: any) => {
        if (r.status !== 200) throw new Error("Personnel verification was not accepted");
        return r.data;
      }),
    onSuccess: () => {
      setActionError("");
      setRejectingUploadId("");
      setRejectionReason("");
      setHistoryPage(0);
      setQueuePage(0);
      qc.invalidateQueries({ queryKey: ["personnel-uploads", personId] });
      qc.invalidateQueries({ queryKey: ["personnel-upload-verification-queue"] });
    },
    onError: (error: unknown) => setActionError(getErrorMessage(error, "Unable to update this credential. Please try again.")),
  });

  const statusColor = (s: string) => {
    if (s === "verified") return "bg-green-100 text-green-800";
    if (s === "rejected") return "bg-red-100 text-red-800";
    return "bg-yellow-100 text-yellow-800";
  };

  const statusIcon = (s: string) => {
    if (s === "verified") return <CheckCircle size={14} className="text-green-600" />;
    if (s === "rejected") return <AlertTriangle size={14} className="text-red-600" />;
    return <Clock size={14} className="text-yellow-600" />;
  };

  const uploadRules = {
    file: { required: "Please select a file to upload." },
  } as const;

  const { errors: uploadFieldErrors, isValid: uploadIsValid } = useValidation(
    { ...uploadForm, file: selectedFile ? "file" : "" },
    uploadRules
  );

  const handleUpload = () => {
    setUploadError("");
    if (!uploadIsValid) {
      setUploadError("Please correct the fields marked below.");
      return;
    }
    createMutation.mutate({ ...uploadForm, file: selectedFile! });
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Personnel & Compliance</div>
          <h1 className="app-title">Self-Service Upload</h1>
          <p className="app-subtitle">Upload your credential documents for verification by the compliance team.</p>
        </div>
        {hasPermission("personnel:view") && (
          <button onClick={() => setShowUpload(true)} className="app-btn-primary flex items-center gap-1">
            <Upload size={16} /> Upload Credential
          </button>
        )}
      </header>

      <Modal open={showUpload} onClose={() => setShowUpload(false)} title="Upload Credential Document" description="Upload your own clear, legible credential file. It will be held for verification.">
        {uploadError && (
          <div role="alert" className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
            {uploadError}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <FormField htmlFor="license_type_118" label="Credential type" required>
            <select id="license_type_118" name="license_type" className="border border-kfl-border rounded p-2 text-sm w-full" value={uploadForm.license_type} onChange={e => { setUploadForm({ ...uploadForm, license_type: e.target.value }); setDirty(true); }}>
              {DOCUMENT_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </FormField>
          <FormField htmlFor="document_type_125" label="Document type" required>
            <select id="document_type_125" name="document_type" className="border border-kfl-border rounded p-2 text-sm w-full" value={uploadForm.document_type} onChange={e => { setUploadForm({ ...uploadForm, document_type: e.target.value }); setDirty(true); }}>
              <option value="license_copy">License Copy</option><option value="certificate">Certificate</option><option value="medical_cert">Medical Certificate</option><option value="training_record">Training Record</option><option value="other">Other</option>
            </select>
          </FormField>
          <FormField htmlFor="file_136" label="Credential file" hint="PDF, PNG, or JPEG; maximum 10 MiB." required className="col-span-2">
            <input id="file_136" name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" aria-describedby="file_136-error" aria-invalid={!!uploadFieldErrors.file} className={`border border-kfl-border rounded p-2 text-sm w-full ${uploadFieldErrors.file ? "border-rose-400" : ""}`} onChange={e => { setSelectedFile(e.target.files?.[0] || null); setDirty(true); }} />
            {uploadFieldErrors.file && <p id="file_136-error" className="text-[11px] text-rose-700 mt-1">{uploadFieldErrors.file}</p>}
          </FormField>
        </div>
        <div className="mt-4 flex gap-2 justify-end">
          <button onClick={() => { setShowUpload(false); setDirty(false); }} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          <button onClick={handleUpload} className="app-btn-primary px-4 py-2 text-sm" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Uploading…" : "Submit for Verification"}
          </button>
        </div>
      </Modal>

      <section className="app-surface overflow-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold text-kfl-text">Your Uploads</h2>
          <div className="flex gap-2">
            {["", "pending", "verified", "rejected"].map(s => (
              <button key={s} onClick={() => { setStatusFilter(s); setHistoryPage(0); }} className={`text-xs px-2 py-1 rounded ${statusFilter === s ? "bg-kfl-primary text-white" : "text-kfl-muted hover:bg-kfl-surface-subtle"}`}>
                {s || "All"}
              </button>
            ))}
          </div>
        </div>
        {actionError && <div role="alert" className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">{actionError}</div>}
        {isError ? (
          <div role="alert" className="p-6 text-center text-rose-800">
            <p>Unable to load your uploads: {getErrorMessage(loadError, "Please try again.")}</p>
            <button onClick={() => void refetch()} className="app-btn-secondary mt-3">Retry loading uploads</button>
          </div>
        ) : isLoading ? (
          <div className="p-10 text-center text-kfl-muted">Loading uploads…</div>
        ) : filteredUploads.length === 0 ? (
          <div className="p-10 text-center text-kfl-muted">No uploads found. Upload a credential document to get started.</div>
        ) : (
          <div className="space-y-3">
            {filteredUploads.map((u: any) => (
              <div key={u.upload_id} className="border border-kfl-border rounded p-3 hover:bg-kfl-surface-subtle">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="font-medium text-kfl-text">{u.file_name}</h4>
                    <div className="text-sm text-kfl-muted">{u.license_type.replace(/_/g, " ")} • {u.document_type.replace(/_/g, " ")}</div>
                  </div>
                  <div className="text-right">
                    <div className={`flex items-center gap-1 ${statusColor(u.verification_status)}`}>
                      {statusIcon(u.verification_status)}
                      <span className="text-xs font-semibold">{u.verification_status}</span>
                    </div>
                    {u.verification_status === "verified" && u.verified_at && <div className="text-xs text-kfl-muted mt-1">Verified by {u.verified_by || "unknown reviewer"} on {u.verified_at}</div>}
                    {u.verification_status === "rejected" && u.updated_at && <div className="text-xs text-kfl-muted mt-1">Rejected by {u.updated_by || "unknown reviewer"} on {u.updated_at}</div>}
                    {u.rejection_reason && <div className="text-xs text-red-600 mt-1">Reason: {u.rejection_reason}</div>}
                  </div>
                </div>
                <div className="text-xs text-kfl-muted mb-2">{u.file_size || 0} bytes, {u.content_type || "—"}</div>
                {u.download_url && <a href={u.download_url} download className="inline-flex items-center gap-1 text-xs font-medium text-kfl-blue hover:underline">
                  <Download size={13} /> Download {u.file_name}
                </a>}
              </div>
            ))}
          </div>
        )}
        {!isLoading && !isError && (historyPage > 0 || uploadsPageData.hasNext) && (
          <div className="mt-4 flex items-center justify-between border-t border-kfl-border pt-4 text-sm">
            <span className="text-kfl-muted">Page {historyPage + 1}</span>
            <div className="flex gap-2">
              <button
                type="button"
                aria-label="Previous upload history page"
                disabled={historyPage === 0 || isLoading}
                onClick={() => setHistoryPage((current) => Math.max(0, current - 1))}
                className="app-btn-secondary text-xs"
              >
                Previous
              </button>
              <button
                type="button"
                aria-label="Next upload history page"
                disabled={!uploadsPageData.hasNext || isLoading}
                onClick={() => setHistoryPage((current) => current + 1)}
                className="app-btn-secondary text-xs"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>

      {canReadPersonnel && <section className="app-surface mt-5 overflow-hidden">
        <div className="border-b border-kfl-border p-4">
          <h2 className="font-semibold text-kfl-text">Verification queue</h2>
          <p className="mt-1 text-xs text-kfl-muted">Review the submitted document itself before recording a decision.</p>
        </div>
        {queueError ? (
          <div role="alert" className="p-6 text-center text-rose-800">
            <p>Unable to load the verification queue.</p>
            <button type="button" onClick={() => void refetchQueue()} className="app-btn-secondary mt-3">Retry verification queue</button>
          </div>
        ) : queueLoading ? (
          <div className="p-8 text-center text-sm text-kfl-muted">Loading verification queue…</div>
        ) : verificationQueue.length === 0 ? (
          <div className="p-8 text-center text-sm text-kfl-muted">No uploads awaiting verification.</div>
        ) : (
          <div className="space-y-3 p-4">
            {verificationQueue.map((upload: any) => (
              <div key={upload.upload_id} className="rounded border border-kfl-border p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-kfl-text">{upload.file_name}</h3>
                    <p className="mt-1 text-sm text-kfl-muted">Person {upload.person_id} · {upload.license_type.replace(/_/g, " ")} · {upload.document_type.replace(/_/g, " ")}</p>
                    <p className="mt-1 text-xs text-kfl-muted">{upload.file_size || 0} bytes · {upload.content_type || "—"}</p>
                  </div>
                  {upload.download_url && <a href={upload.download_url} download className="inline-flex items-center gap-1 text-xs font-medium text-kfl-blue hover:underline">
                    <Download size={13} /> Download {upload.file_name}
                  </a>}
                </div>
                {canManagePersonnel && !canReviewUpload(upload) ? (
                  <p className="mt-3 text-xs text-kfl-muted">This upload cannot be reviewed by the current account.</p>
                ) : canManagePersonnel && canReviewUpload(upload) && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button type="button" disabled={verifyMutation.isPending} aria-label={`Verify ${upload.upload_id}`} onClick={() => verifyMutation.mutate({ id: upload.upload_id, status: "verified" })} className="app-btn-secondary inline-flex items-center gap-1 text-xs">
                      <CheckCircle size={13} /> Verify
                    </button>
                    <button type="button" disabled={verifyMutation.isPending} aria-label={`Reject ${upload.upload_id}`} onClick={() => { setRejectingUploadId(upload.upload_id); setRejectionReason(""); }} className="app-btn-secondary inline-flex items-center gap-1 text-xs text-red-700">
                      <AlertTriangle size={13} /> Reject
                    </button>
                    {rejectingUploadId === upload.upload_id && (
                      <div className="mt-2 w-full space-y-2">
                        <FormField htmlFor={`rejection_reason_${upload.upload_id}`} label={`Rejection reason for ${upload.upload_id}`} required>
                          <textarea id={`rejection_reason_${upload.upload_id}`} name="rejection_reason" rows={2} className="app-input" value={rejectionReason} onChange={(e) => setRejectionReason(e.target.value)} />
                        </FormField>
                        <div className="flex gap-2">
                          <button type="button" disabled={!rejectionReason.trim() || verifyMutation.isPending} onClick={() => verifyMutation.mutate({ id: upload.upload_id, status: "rejected", reason: rejectionReason.trim() })} className="app-btn-primary text-xs">Confirm rejection</button>
                          <button type="button" onClick={() => { setRejectingUploadId(""); setRejectionReason(""); }} className="app-btn-secondary text-xs">Cancel</button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {(queuePage > 0 || queuePageData.hasNext) && (
          <div className="flex items-center justify-between border-t border-kfl-border p-4 text-sm">
            <span className="text-kfl-muted">Page {queuePage + 1}</span>
            <div className="flex gap-2">
              <button
                type="button"
                aria-label="Previous verification queue page"
                disabled={queuePage === 0 || queueLoading}
                onClick={() => setQueuePage((current) => Math.max(0, current - 1))}
                className="app-btn-secondary text-xs"
              >
                Previous
              </button>
              <button
                type="button"
                aria-label="Next verification queue page"
                disabled={!queuePageData.hasNext || queueLoading}
                onClick={() => setQueuePage((current) => current + 1)}
                className="app-btn-secondary text-xs"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>}
    </div>
  );
}

export default SelfServiceUpload;
