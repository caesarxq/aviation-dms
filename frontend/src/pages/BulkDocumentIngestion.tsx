import { useState } from "react";
import { Upload, FileText, Loader2, Plus, File, X } from "lucide-react";
import { p2Api } from "../api/p2";
import { useToast } from "../components/ui/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

const MAX_FILES = 25;
const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";

interface BulkItem {
  staging_id: string;
  file_name: string;
  document_type: string;
  confidence: number;
  target_table: string;
  status: string;
  extracted_fields: Record<string, any>;
  raw_text_preview: string;
  duplicate_of?: string;
}

interface BatchResult {
  batch_id: string;
  items: BulkItem[];
  staged: number;
  duplicates: number;
  rejected: number;
}

type FieldType = "text" | "date" | "select";

interface FieldConfig {
  label: string;
  key: string;
  type: FieldType;
  options?: string[];
}

interface TargetFieldConfig extends FieldConfig {
  required?: boolean;
}

const STATUS_BADGE: Record<string, { variant: "default" | "secondary" | "destructive"; label: string }> = {
  staged: { variant: "default", label: "Staged" },
  duplicate: { variant: "secondary", label: "Duplicate" },
  rejected: { variant: "destructive", label: "Rejected" },
  applied: { variant: "default", label: "Applied" },
};

const EXTRACTED_FIELD_CONFIGS: Record<string, FieldConfig[]> = {
  documents: [
    { label: "Title", key: "title", type: "text" },
    { label: "Document Class", key: "doc_class", type: "select", options: ["operations_manual", "safety_manual", "maintenance_manual", "training_manual", "emergency_plan", "policy", "procedure", "import_permit", "temporary_import_permit"] },
    { label: "Description", key: "description", type: "text" },
    { label: "Issue Revision", key: "source_issue_revision", type: "text" },
    { label: "Issue Date", key: "source_issued_date", type: "date" },
  ],
  aircraft_insurance: [
    { label: "Insurance Type", key: "insurance_type", type: "select", options: ["hull", "liability", "war_risk", "passenger_liability", "cargo_liability"] },
    { label: "Policy Number", key: "policy_number", type: "text" },
    { label: "Insurer", key: "insurer", type: "text" },
    { label: "Coverage Amount", key: "coverage_amount", type: "text" },
    { label: "Start Date", key: "start_date", type: "date" },
    { label: "Expiry Date", key: "expiry_date", type: "date" },
  ],
  aircraft_documents: [
    { label: "Document Type", key: "document_type", type: "select", options: ["airworthiness_cert", "registration", "arc", "noise_cert", "radio_license", "maintenance_release"] },
    { label: "Document Number", key: "document_number", type: "text" },
    { label: "Issuing Authority", key: "issuing_authority", type: "text" },
    { label: "Issue Date", key: "issue_date", type: "date" },
    { label: "Expiry Date", key: "expiry_date", type: "date" },
  ],
  personnel_licenses: [
    { label: "License Type", key: "license_type", type: "select", options: ["pilot_license", "medical", "type_rating", "proficiency_check", "english_proficiency"] },
    { label: "License Number", key: "license_number", type: "text" },
    { label: "Issuing Authority", key: "issuing_authority", type: "text" },
    { label: "Issued Date", key: "issued_date", type: "date" },
    { label: "Expiry Date", key: "expiry_date", type: "date" },
  ],
  audit_report_import: [
    { label: "Audit Number", key: "audit_number", type: "text" },
    { label: "Audit Date", key: "audit_date", type: "date" },
    { label: "Scope", key: "scope", type: "text" },
    { label: "Regulatory Basis", key: "regulatory_basis", type: "text" },
  ],
};

const TARGET_SPECIFIC_CONFIGS: Record<string, TargetFieldConfig[]> = {
  documents: [{ label: "Document ID", key: "document_id", type: "text", required: true }],
  aircraft_insurance: [{ label: "Aircraft ID", key: "aircraft_id", type: "text", required: true }],
  aircraft_documents: [{ label: "Aircraft ID", key: "aircraft_id", type: "text", required: true }],
  personnel_licenses: [{ label: "Person ID", key: "person_id", type: "text", required: true }],
  audit_report_import: [
    { label: "Source Auditor ID", key: "source_auditor_id", type: "text", required: true },
    { label: "Source Auditor Name", key: "source_auditor_name", type: "text", required: true },
    { label: "Auditee ID", key: "auditee_id", type: "text", required: true },
    { label: "Audit Number", key: "audit_number", type: "text", required: true },
    { label: "Audit Date", key: "audit_date", type: "date", required: true },
    { label: "Scope", key: "scope", type: "text" },
    { label: "Regulatory Basis", key: "regulatory_basis", type: "text" },
  ],
};

export function BulkDocumentIngestion() {
  const { toast } = useToast();
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [batch, setBatch] = useState<BatchResult | null>(null);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [editedFields, setEditedFields] = useState<Record<string, Record<string, string>>>({});
  const [targetSpecific, setTargetSpecific] = useState<Record<string, Record<string, string>>>({});
  const [selectedForApply, setSelectedForApply] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<"all" | "staged" | "duplicate" | "rejected">("all");

  const handleFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []).filter((f) => {
      const ext = (f.name.split(".").pop() ?? "").toLowerCase();
      return ["pdf", "png", "jpg", "jpeg"].includes(ext);
    });
    if (selected.length > MAX_FILES) {
      toast({ title: "Too many files", message: `Maximum ${MAX_FILES} files per batch.`, type: "error" });
      return;
    }
    setFiles(selected);
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setApplyError(null);
    setBatch(null);
    setEditedFields({});
    setTargetSpecific({});
    setSelectedForApply(new Set());
    try {
      const result: BatchResult = await p2Api.bulkIngestDocument(files);
      setBatch(result);
      result.items.forEach((item) => {
        if (item.status === "staged") {
          const fields: Record<string, string> = {};
          for (const [k, v] of Object.entries(item.extracted_fields ?? {})) {
            fields[k] = v != null ? String(v) : "";
          }
          setEditedFields((prev) => ({ ...prev, [item.staging_id]: fields }));
          setTargetSpecific((prev) => ({ ...prev, [item.staging_id]: {} }));
          setSelectedForApply((prev) => new Set([...prev, item.staging_id]));
        }
      });
      toast({
        title: "Batch ingested",
        message: `${result.staged} staged, ${result.duplicates} duplicate(s), ${result.rejected} rejected.`,
        type: result.rejected === 0 && result.staged > 0 ? "success" : "warning",
      });
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Bulk ingestion failed.";
      setApplyError(detail);
      toast({ title: "Ingestion failed", message: detail, type: "error" });
    } finally {
      setUploading(false);
    }
  };

  const handleFieldChange = (stagingId: string, key: string, value: string) => {
    setEditedFields((prev) => ({ ...prev, [stagingId]: { ...prev[stagingId], [key]: value } }));
  };

  const handleTargetFieldChange = (stagingId: string, key: string, value: string) => {
    setTargetSpecific((prev) => ({ ...prev, [stagingId]: { ...prev[stagingId], [key]: value } }));
  };

  const handleSelect = (stagingId: string, checked: boolean) => {
    setSelectedForApply((prev) => {
      const next = new Set(prev);
      if (checked) next.add(stagingId);
      else next.delete(stagingId);
      return next;
    });
  };

  const toggleSelectAll = (checked: boolean) => {
    if (!batch) return;
    const stagedIds = batch.items.filter((i) => i.status === "staged").map((i) => i.staging_id);
    setSelectedForApply(checked ? new Set(stagedIds) : new Set());
  };

  const handleApply = async () => {
    if (!batch) return;
    setApplying(true);
    setApplyError(null);
    try {
      const items = batch.items
        .filter((i) => i.status === "staged" && selectedForApply.has(i.staging_id))
        .map((i) => ({
          staging_id: i.staging_id,
          target_table: i.target_table,
          ...editedFields[i.staging_id],
          ...targetSpecific[i.staging_id],
        }));
      if (items.length === 0) {
        setApplyError("Select at least one staged item to apply.");
        return;
      }
      await p2Api.applyBulkIngestionDocument({ items });
      setBatch((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.map((i) =>
                i.status === "staged" && selectedForApply.has(i.staging_id)
                  ? { ...i, status: "applied" }
                  : i
              ),
            }
          : prev
      );
      toast({ title: "Items applied", message: `${items.length} record(s) promoted.`, type: "success" });
      setSelectedForApply(new Set());
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Unable to apply the selected items.";
      setApplyError(detail);
      toast({ title: "Apply failed", message: detail, type: "error" });
    } finally {
      setApplying(false);
    }
  };

  const resetBatch = () => {
    setFiles([]);
    setBatch(null);
    setEditedFields({});
    setTargetSpecific({});
    setSelectedForApply(new Set());
    setApplyError(null);
    const input = document.getElementById("bulk-file-input") as HTMLInputElement | null;
    if (input) input.value = "";
  };

  const stagedCount = batch ? batch.items.filter((i) => i.status === "staged").length : 0;
  const filteredItems = batch
    ? batch.items.filter((i) => {
        if (filter === "all") return true;
        return i.status === filter;
      })
    : [];

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Documents Section</div>
          <h1 className="app-title">Bulk Document Intake</h1>
          <p className="app-subtitle">
            Upload historical records (KCAA correspondence, OAs, registration certificates, insurance
            policies, personnel licenses, mission sheets, flight logs) in batches of up to{" "}
            {MAX_FILES} files. Each file is classified and staged for review before promotion.
            Historical audits, CARs and findings reports are quarantined to{" "}
            <code className="text-xs">audit_report_imports</code> pending provenance verification.
          </p>
        </div>
        <Button onClick={resetBatch} variant="outline" size="sm" disabled={uploading}>
          {uploading ? <Loader2 size={14} className="mr-2" /> : "Reset"}
        </Button>
      </header>

      {!batch ? (
        <div className="app-surface p-6 max-w-3xl">
          <div
            className="border-2 border-dashed border-kfl-border rounded-lg p-10 text-center hover:border-kfl-blue transition-colors cursor-pointer"
            onClick={() => document.getElementById("bulk-file-input")?.click()}
          >
            <div className="flex flex-col items-center gap-3">
              <Upload size={36} className="text-kfl-blue" />
              <Plus size={16} className="text-kfl-muted" />
              <p className="text-sm font-semibold text-kfl-text mb-1">Click to upload files</p>
              <p className="text-xs text-kfl-muted">
                PDF, PNG, JPEG &bull; max 10 MiB each &bull; max {MAX_FILES} files per batch
              </p>
              <input
                id="bulk-file-input"
                type="file"
                multiple
                accept={ACCEPT}
                className="hidden"
                onChange={handleFilesChange}
              />
              {files.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                  {files.map((f) => (
                    <span key={f.name + f.size} className="flex items-center gap-1 px-2 py-1 rounded border border-kfl-border bg-kfl-surface-subtle text-xs text-kfl-text">
                      <File size={10} className="mr-1" />
                      {f.name}
                      <button
                        type="button"
                        onClick={() => setFiles(files.filter((x) => x !== f))}
                        className="ml-1 text-xs text-kfl-muted hover:text-kfl-status-danger"
                      >
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                  <p className="ml-2 text-[10px] text-kfl-muted">{files.length}/{MAX_FILES}</p>
                </div>
              )}
            </div>
            <Button
              onClick={handleUpload}
              disabled={uploading || files.length === 0}
              variant="default"
              className="mt-6"
            >
              {uploading ? <Loader2 size={16} className="mr-2" /> : "Stage & Classify Batch"}
            </Button>
            {applyError && (
              <div role="alert" className="mt-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                {applyError}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="max-w-5xl">
          <div className="app-surface p-4 mb-4">
            <div className="flex flex-wrap gap-4 items-center">
              <div className="flex-1 min-w-[120px]">
                <p className="text-xs text-kfl-muted uppercase tracking-wider">Batch ID</p>
                <p className="text-sm font-mono text-kfl-text">{batch.batch_id}</p>
              </div>
              <div className="flex-1 min-w-[140px]">
                <p className="text-xs text-kfl-muted uppercase tracking-wider">Staged</p>
                <p className="text-sm font-bold text-kfl-status-success">{batch.staged}</p>
              </div>
              <div className="flex-1 min-w-[140px]">
                <p className="text-xs text-kfl-muted uppercase tracking-wider">Duplicates</p>
                <p className="text-sm font-bold text-kfl-muted">{batch.duplicates}</p>
              </div>
              <div className="flex-1 min-w-[140px]">
                <p className="text-xs text-kfl-muted uppercase tracking-wider">Rejected</p>
                <p className="text-sm font-bold text-kfl-status-danger">{batch.rejected}</p>
              </div>
            </div>
          </div>

          <div className="flex gap-2 mb-3">
            {(["all", "staged", "duplicate", "rejected"] as const).map((value) => {
              const label = value.charAt(0).toUpperCase() + value.slice(1);
              return (
                <Button
                  key={value}
                  size="sm"
                  variant={filter === value ? "default" : "outline"}
                  onClick={() => setFilter(value)}
                >
                  {label}
                </Button>
              );
            })}
          </div>

          <div className="space-y-3">
            {filteredItems.length === 0 && (
              <div className="app-surface p-8 text-center text-kfl-muted">
                No items matching filter.
              </div>
            )}
            {filteredItems.map((item: BulkItem) => {
              const isStaged = item.status === "staged";
              const targetSpecificCfg = TARGET_SPECIFIC_CONFIGS[item.target_table];
              const showAuditProvenance = isStaged && item.target_table === "audit_report_import";
              const fieldConfigs = EXTRACTED_FIELD_CONFIGS[item.target_table] || [];
              const currentFields = editedFields[item.staging_id] ?? {};
              const currentTarget = targetSpecific[item.staging_id] ?? {};
              const provisionalFields: TargetFieldConfig[] = showAuditProvenance
                ? TARGET_SPECIFIC_CONFIGS.audit_report_import
                : (targetSpecificCfg ?? []);

              return (
                <div
                  key={item.staging_id}
                  className="rounded border border-kfl-border bg-kfl-surface p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-kfl-text truncate">{item.file_name}</span>
                        <Badge variant="outline" className="text-xs ml-auto">
                          {item.target_table}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-kfl-muted">
                        <span>{item.document_type} &bull;</span>
                        <span>{Math.round(item.confidence * 100)}% confidence</span>
                        {item.status === "duplicate" && item.duplicate_of && (
                          <span>Duplicate of {item.duplicate_of}</span>
                        )}
                      </div>
                    </div>
                    <Badge
                      variant={STATUS_BADGE[item.status]?.variant ?? "secondary"}
                      className="text-xs"
                    >
                      {STATUS_BADGE[item.status]?.label ?? item.status}
                    </Badge>
                  </div>

                  {isStaged && (
                    <div className="space-y-3">
                      <div className="rounded border border-kfl-border/50 bg-kfl-surface-subtle p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <FileText size={12} className="text-kfl-blue" />
                          <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">
                            Extracted Fields (review & edit)
                          </span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {fieldConfigs.map((field: FieldConfig) => (
                            <div key={field.key} className="col-span-2 sm:col-span-1">
                              <label className="text-[10px] font-semibold text-kfl-muted block mb-1">
                                {field.label}
                              </label>
                              {field.type === "select" ? (
                                <Select
                                  onValueChange={(v: string) =>
                                    handleFieldChange(item.staging_id, field.key, v)
                                  }
                                >
                                  <SelectTrigger>
                                    <SelectValue placeholder={currentFields[field.key] ?? ""} />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {field.options!.map((o: string) => (
                                      <SelectItem key={o} value={o}>
                                        {o.replace(/_/g, " ")}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              ) : (
                                <Input
                                  value={currentFields[field.key] ?? ""}
                                  onChange={(e) =>
                                    handleFieldChange(item.staging_id, field.key, e.target.value)
                                  }
                                  className="w-full text-xs"
                                  placeholder={field.type === "date" ? "YYYY-MM-DD" : undefined}
                                />
                              )}
                            </div>
                          ))}
                        </div>
                        <div className="mt-2 pt-2 border-t border-kfl-border/50">
                          <label className="text-[10px] font-semibold text-kfl-muted block mb-1">
                            Raw Extracted Text (preview)
                          </label>
                          <Textarea
                            value={item.raw_text_preview}
                            readOnly
                            rows={2}
                            className="w-full text-[10px] text-kfl-muted font-mono bg-kfl-surface rounded p-2"
                          />
                        </div>
                      </div>

                      {(showAuditProvenance || targetSpecificCfg) && (
                        <div className="rounded border border-kfl-border/50 bg-kfl-surface p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">
                              {showAuditProvenance ? "Provenance (required for audit import)" : "Target Record"}
                            </span>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {provisionalFields.map((field: TargetFieldConfig) => (
                              <div key={field.key} className="col-span-2 sm:col-span-1">
                                <label className="text-[10px] font-semibold text-kfl-muted block mb-1">
                                  {field.label}
                                  {field.required && (
                                    <span className="text-kfl-status-danger"> *</span>
                                  )}
                                </label>
                                <Input
                                  value={currentTarget[field.key] ?? ""}
                                  onChange={(e) =>
                                    handleTargetFieldChange(item.staging_id, field.key, e.target.value)
                                  }
                                  className="w-full text-xs"
                                  placeholder={field.type === "date" ? "YYYY-MM-DD" : undefined}
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex items-center gap-2 mt-2">
                        <input
                          type="checkbox"
                          checked={selectedForApply.has(item.staging_id)}
                          onChange={(e) => handleSelect(item.staging_id, e.target.checked)}
                          className="rounded border-kfl-border text-kfl-blue focus:ring-kfl-blue"
                        />
                        <span className="text-xs text-kfl-text">Apply this item</span>
                      </div>
                    </div>
                  )}
                  {!isStaged && item.status !== "staged" && (
                    <div className="text-xs text-kfl-muted mt-2">
                      {item.status === "duplicate"
                        ? `Already ingested as ${item.duplicate_of}.`
                        : "Rejected during intake (see batch summary)."}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-6 flex items-center justify-between border-t border-kfl-border pt-4">
            <div className="text-xs text-kfl-muted">
              {selectedForApply.size} of {stagedCount} staged item(s) selected
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => toggleSelectAll(selectedForApply.size < stagedCount)}
                variant="outline"
                size="sm"
                disabled={applying || stagedCount === 0}
              >
                {selectedForApply.size === stagedCount && stagedCount > 0 ? "Select None" : "Select All Staged"}
              </Button>
              <Button
                onClick={handleApply}
                disabled={applying || selectedForApply.size === 0}
                variant="default"
              >
                {applying ? <Loader2 size={16} className="mr-2" /> : "Apply Selected"}
              </Button>
            </div>
          </div>
          {applyError && (
            <div role="alert" className="mt-3 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
              {applyError}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default BulkDocumentIngestion;
