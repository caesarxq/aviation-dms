import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Upload, CheckCircle, Clock, AlertTriangle } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";

const DOCUMENT_TYPES = [
  "pilot_license", "medical", "type_rating", "proficiency_check",
  "dg_training", "security_training", "sms_awareness", "crm",
  "indoctrination", "background_check", "english_proficiency", "avsec",
];

export function SelfServiceUpload() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [personId] = useState("u-safety"); // default actor
  const [statusFilter, setStatusFilter] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    person_id: personId, license_type: "pilot_license", document_type: "license_copy",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");

  const { data: uploads = [], isLoading } = useQuery({
    queryKey: ["personnel-uploads", personId],
    queryFn: () => personId
      ? api.get(`/p2/personnel/uploads/${personId}`).then((r: any) => r.data)
      : Promise.resolve([]),
    enabled: !!personId,
  });

  const filteredUploads = uploads.filter((u: any) => !statusFilter || u.verification_status === statusFilter);

  const createMutation = useMutation({
    mutationFn: (data: { person_id: string; license_type: string; document_type: string; file: File }) => {
      const formData = new FormData();
      formData.append("person_id", data.person_id);
      formData.append("license_type", data.license_type);
      formData.append("document_type", data.document_type);
      formData.append("file", data.file);
      return api.post("/p2/personnel/uploads/file", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      }).then((r: any) => r.data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["personnel-uploads", personId] });
      setShowUpload(false);
      setUploadError("");
      setUploadForm({ person_id: personId, license_type: "pilot_license", document_type: "license_copy" });
      setSelectedFile(null);
      toast({ title: "Credential uploaded", message: "Your document has been submitted for verification.", type: "success" });
    },
    onError: () => {
      setUploadError("Failed to upload credential. Please try again.");
    },
  });

  const verifyMutation = useMutation({
    mutationFn: ({ id, status, reason }: { id: string; status: string; reason?: string }) =>
      api.patch(`/p2/personnel/uploads/${id}/verify`, { verification_status: status, rejection_reason: reason }).then((r: any) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personnel-uploads", personId] }),
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

  const handleUpload = () => {
    setUploadError("");
    if (!uploadForm.person_id.trim()) {
      setUploadError("Your Person ID is required.");
      return;
    }
    if (!selectedFile) {
      setUploadError("Please select a file to upload.");
      return;
    }
    createMutation.mutate({ ...uploadForm, file: selectedFile });
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Personnel & Compliance</div>
          <h1 className="app-title">Self-Service Upload</h1>
          <p className="app-subtitle">Upload your credential documents for verification by the compliance team.</p>
        </div>
        <button onClick={() => setShowUpload(true)} className="app-btn-primary flex items-center gap-1">
          <Upload size={16} /> Upload Credential
        </button>
      </header>

      {/* Upload Credential Modal */}
      <Modal open={showUpload} onClose={() => setShowUpload(false)} title="Upload Credential Document" description="Upload a clear, legible credential file belonging to the selected person. Confirm the credential type before choosing the file; the document will be held for verification.">
        {uploadError && (
          <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
            {uploadError}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <input id="your_person_id_112" name="your_person_id"
            className="border border-kfl-border rounded p-2 text-sm"
            placeholder="Your Person ID (e.g., u-safety)"
            value={uploadForm.person_id}
            onChange={e => setUploadForm({ ...uploadForm, person_id: e.target.value })}
          />
          <select id="license_type_118" name="license_type"
            className="border border-kfl-border rounded p-2 text-sm"
            value={uploadForm.license_type}
            onChange={e => setUploadForm({ ...uploadForm, license_type: e.target.value })}
          >
            {DOCUMENT_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
          <select id="document_type_125" name="document_type"
            className="border border-kfl-border rounded p-2 text-sm"
            value={uploadForm.document_type}
            onChange={e => setUploadForm({ ...uploadForm, document_type: e.target.value })}
          >
            <option value="license_copy">License Copy</option>
            <option value="certificate">Certificate</option>
            <option value="medical_cert">Medical Certificate</option>
            <option value="training_record">Training Record</option>
            <option value="other">Other</option>
          </select>
          <input id="file_136" name="file"
            type="file"
            className="border border-kfl-border rounded p-2 text-sm col-span-2"
            onChange={e => setSelectedFile(e.target.files?.[0] || null)}
          />
        </div>
        <div className="mt-4 flex gap-2 justify-end">
          <button onClick={() => setShowUpload(false)} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          <button onClick={handleUpload} className="app-btn-primary px-4 py-2 text-sm" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Uploading…" : "Submit for Verification"}
          </button>
        </div>
      </Modal>

      {/* Uploads list */}
      <section className="app-surface overflow-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold text-kfl-text">Your Uploads</h2>
          <div className="flex gap-2">
            {["", "pending", "verified", "rejected"].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} className={`text-xs px-2 py-1 rounded ${statusFilter === s ? "bg-kfl-primary text-white" : "text-kfl-muted hover:bg-kfl-surface-subtle"}`}>
                {s || "All"}
              </button>
            ))}
          </div>
        </div>
        {isLoading ? (
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
                    {u.verified_at && <div className="text-xs text-kfl-muted mt-1">Verified: {u.verified_at}</div>}
                    {u.rejection_reason && <div className="text-xs text-red-600 mt-1">Reason: {u.rejection_reason}</div>}
                  </div>
                </div>
                <div className="text-xs text-kfl-muted mb-2">{u.file_path} ({u.file_size || 0} bytes, {u.content_type || "—"})</div>
                {u.verification_status === "pending" && (
                  <div className="flex gap-2">
                    <button onClick={() => verifyMutation.mutate({ id: u.upload_id, status: "verified" })} className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1"><CheckCircle size={12} /> Verify</button>
                    <button onClick={() => verifyMutation.mutate({ id: u.upload_id, status: "rejected", reason: "Needs revision" })} className="text-xs text-red-600 hover:text-red-800 flex items-center gap-1"><AlertTriangle size={12} /> Reject</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default SelfServiceUpload;
