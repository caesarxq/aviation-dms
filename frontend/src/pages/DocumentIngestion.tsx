import { useState } from "react";
import { Upload, FileText, Info } from "lucide-react";
import { p2Api } from "../api/p2";
import { useToast } from "../components/ui/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface IngestionResult {
  document_type: string;
  confidence: number;
  extracted_fields: Record<string, any>;
  target_table: string;
  raw_text_preview: string;
}

interface ExtractedField {
  label: string;
  key: string;
  type: "text" | "date" | "number" | "select";
  options?: string[];
}

const FIELD_CONFIGS: Record<string, ExtractedField[]> = {
  aircraft_insurance: [
    { label: "Insurance Type", key: "insurance_type", type: "select", options: ["hull", "liability", "war_risk", "passenger_liability", "cargo_liability"] },
    { label: "Policy Number", key: "policy_number", type: "text" },
    { label: "Insurer", key: "insurer", type: "text" },
    { label: "Broker", key: "broker", type: "text" },
    { label: "Coverage Amount", key: "coverage_amount", type: "number" },
    { label: "Currency", key: "currency", type: "text" },
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
    { label: "Aircraft Type", key: "aircraft_type", type: "text" },
  ],
  documents: [
    { label: "Title", key: "title", type: "text" },
    { label: "Document Class", key: "doc_class", type: "select", options: ["operations_manual", "safety_manual", "maintenance_manual", "training_manual", "emergency_plan", "policy", "procedure", "import_permit", "temporary_import_permit"] },
    { label: "Description", key: "description", type: "text" },
    { label: "Issue Revision", key: "source_issue_revision", type: "text" },
    { label: "Issue Date", key: "source_issued_date", type: "date" },
  ],
};

const TABLE_LABELS: Record<string, string> = {
  aircraft_insurance: "Aircraft Insurance Policy",
  aircraft_documents: "Aircraft Document (Registration, CoA, etc.)",
  personnel_licenses: "Personnel License",
  documents: "Controlled Document / Policy",
};

export function DocumentIngestion() {
  const { toast } = useToast();

  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [extractedFields, setExtractedFields] = useState<Record<string, string>>({});
  const [targetSpecific, setTargetSpecific] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setApplyError(null);
    try {
      const data = await p2Api.ingestDocument(file);
      setResult(data);
      const fields: Record<string, string> = {};
      for (const [key, value] of Object.entries(data.extracted_fields)) {
        fields[key] = value != null ? String(value) : "";
      }
      setExtractedFields(fields);
      toast({ title: "Document ingested", message: `Extracted ${data.document_type} with ${Math.round(data.confidence * 100)}% confidence.`, type: "success" });
    } catch (err: any) {
      toast({ title: "Ingestion failed", message: err?.response?.data?.detail || "Unable to extract text from the PDF.", type: "error" });
    } finally {
      setUploading(false);
    }
  };

  const handleFieldChange = (key: string, value: string) => {
    setExtractedFields((prev) => ({ ...prev, [key]: value }));
  };

  const handleApply = async () => {
    if (!result) return;
    setApplying(true);
    setApplyError(null);
    try {
      await p2Api.applyIngestion({
        document_type: result.document_type,
        target_table: result.target_table,
        extracted_fields: extractedFields,
        ...targetSpecific,
      });
      toast({ title: "Document applied", message: `Record created in ${TABLE_LABELS[result.target_table]}. Awaiting verification.`, type: "success" });
      setFile(null);
      setResult(null);
      setExtractedFields({});
      setTargetSpecific({});
    } catch (err: any) {
      setApplyError(err?.response?.data?.detail || "Unable to apply the ingested document.");
      toast({ title: "Apply failed", message: applyError || "Unable to apply the document.", type: "error" });
    } finally {
      setApplying(false);
    }
  };

  const resetForm = () => {
    const input = document.getElementById("file-input") as HTMLInputElement | null;
    if (input) input.value = "";
    setFile(null);
    setResult(null);
    setExtractedFields({});
    setTargetSpecific({});
    setApplyError(null);
  };

  const fieldsConfig = result ? FIELD_CONFIGS[result.target_table] || [] : [];

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Ingestion</div>
          <h1 className="app-title">Document Ingestion</h1>
          <p className="app-subtitle">
            Upload a PDF credential or certificate (insurance policy, registration, personnel license, or operations authorization).
            Text is auto-extracted and routed to the correct business table for verification.
          </p>
        </div>
      </header>

      {!result ? (
        <div className="app-surface p-6 max-w-2xl">
          <div className="border-2 border-dashed border-kfl-border rounded-lg p-8 text-center hover:border-kfl-blue transition-colors cursor-pointer" onClick={() => document.getElementById("file-input")?.click()}>
            <Upload size={40} className="mx-auto mb-4 text-kfl-blue" />
            <p className="text-sm font-semibold text-kfl-text mb-2">Click to upload PDF</p>
            <p className="text-xs text-kfl-muted">PDF, max 10 MiB. Insurance policies, registration documents, personnel licenses, and operations authorizations are supported.</p>
            <input
              id="file-input"
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) setFile(e.target.files[0]);
              }}
            />
            {file && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <span className="text-xs text-kfl-muted">{file.name}</span>
                <button
                  type="button"
                  onClick={() => {
                    setFile(null);
                    const input = document.getElementById("file-input") as HTMLInputElement | null;
                    if (input) input.value = "";
                  }}
                  className="text-xs text-kfl-status-danger hover:underline"
                >
                  Remove
                </button>
              </div>
            )}
            <Button
              onClick={handleUpload}
              disabled={uploading || !file}
              variant="default"
              className="mt-4"
            >
              {uploading ? "Extracting…" : "Extract & Classify"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="max-w-3xl">
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <h2 className="text-lg font-bold text-kfl-text">Extracted Document</h2>
              <p className="text-xs text-kfl-muted">{result.document_type} • {Math.round(result.confidence * 100)}% confidence</p>
            </div>
            <Badge
              variant={result.confidence >= 0.8 ? "default" : "secondary"}
              className={result.confidence >= 0.8 ? "bg-kfl-status-success-bg text-kfl-status-success" : "bg-kfl-status-warning-bg text-kfl-status-warning"}
            >
              {result.confidence >= 0.8 ? "High confidence" : "Review recommended"}
            </Badge>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <div className="rounded-lg border border-kfl-border p-4">
                <div className="flex items-center gap-2 mb-3">
                  <FileText size={14} className="text-kfl-blue" />
                  <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Extracted Fields</span>
                </div>
                <div className="space-y-3">
                  {fieldsConfig.map((field) => (
                    <div key={field.key} className="space-y-1">
                      <label className="text-xs font-semibold text-kfl-muted">{field.label}</label>
                      <Input
                        value={extractedFields[field.key] ?? ""}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        className="w-full"
                      />
                    </div>
                  ))}
                  <div className="pt-3 border-t border-kfl-border/50">
                    <label className="text-xs font-semibold text-kfl-muted">Raw Extracted Text (preview)</label>
                    <textarea
                      value={result.raw_text_preview}
                      readOnly
                      rows={4}
                      className="w-full text-xs text-kfl-muted font-mono bg-kfl-surface-subtle rounded p-2"
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="lg:col-span-1 space-y-4">
              <div className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Info size={14} className="text-kfl-blue" />
                  <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Target Table</span>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-2 rounded border border-kfl-border bg-kfl-surface">
                    <span className="text-xs text-kfl-text">{TABLE_LABELS[result.target_table]}</span>
                    <span className="text-xs font-mono text-kfl-muted">{result.target_table}</span>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Target Record</span>
                </div>
                <div className="space-y-3">
                  {result.target_table === "aircraft_insurance" || result.target_table === "aircraft_documents" ? (
                                  <FormFieldAdapter
                                    label="Aircraft ID"
                                    hint="Aircraft ID from the ROC fleet register"
                                    value={targetSpecific.aircraft_id ?? ""}
                                    onChange={(v) => setTargetSpecific({ ...targetSpecific, aircraft_id: v })}
                                    placeholder="e.g. AC-001"
                                  />
                                ) : null}
                                {result.target_table === "personnel_licenses" ? (
                                  <FormFieldAdapter
                                    label="Person ID"
                                    hint="Canonical user ID from the personnel register"
                                    value={targetSpecific.person_id ?? ""}
                                    onChange={(v) => setTargetSpecific({ ...targetSpecific, person_id: v })}
                                    placeholder="e.g. u-flight-ops"
                                  />
                                ) : null}
                                {result.target_table === "documents" ? (
                                  <FormFieldAdapter
                                    label="Document ID"
                                    hint="Document ID from the controlled document catalogue"
                                    value={targetSpecific.document_id ?? ""}
                                    onChange={(v) => setTargetSpecific({ ...targetSpecific, document_id: v })}
                                    placeholder="e.g. DOC-001"
                                  />
                                ) : null}
                </div>
              </div>

              <div className="mt-4">
                <Button
                  onClick={handleApply}
                  disabled={applying || !file}
                  variant="default"
                  className="w-full"
                >
                  {applying ? "Applying…" : "Apply & Create Record"}
                </Button>
                {applyError && (
                  <div role="alert" className="mt-3 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                    {applyError}
                  </div>
                )}
                <button
                  type="button"
                  onClick={resetForm}
                  className="mt-2 text-xs text-kfl-muted hover:underline block"
                >
                  Upload another document
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

type FormFieldAdapterProps = {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

function FormFieldAdapter({ label, hint, value, onChange, placeholder }: FormFieldAdapterProps) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-semibold text-kfl-muted">{label}</label>
      {hint && <p className="text-[10px] text-kfl-muted">{hint}</p>}
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full"
      />
    </div>
  );
}

export default DocumentIngestion;
