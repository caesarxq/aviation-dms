import { FormEvent, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { auditApi } from "../api/audit";
import type {
  AuditReportImport,
  AuditReportImportCreate,
  AuditReportImportFindingInput,
  AuditReportImportReview,
} from "../api/audit";
import { useAuth } from "../auth/AuthContext";
import FormField from "./ui/FormField";

const EMPTY_STAGE_FORM = {
  audit_number: "",
  audit_date: "",
  source_auditor_id: "",
  source_auditor_name: "",
  auditee_id: "",
  scope: "",
  regulatory_basis: "",
  evidence_file: "",
  expected_evidence_sha256: "",
};

const IMPORT_PAGE_SIZE = 50;
const IMPORT_FETCH_LIMIT = IMPORT_PAGE_SIZE + 1;

type StageFormFields = typeof EMPTY_STAGE_FORM;

export function AuditReportImportWorkflow() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canImport = hasPermission("audit_report:import");
  const canVerify = hasPermission("audit_report:provenance_verify");
  const canReadQueue = canImport || canVerify;
  const [showStageForm, setShowStageForm] = useState(false);
  const [stageForm, setStageForm] = useState<StageFormFields>(EMPTY_STAGE_FORM);
  const [findingsJson, setFindingsJson] = useState("[]");
  const [stageError, setStageError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [selectedImportId, setSelectedImportId] = useState("");
  const [sourceChecksumConfirmed, setSourceChecksumConfirmed] = useState(false);
  const [findingsReconciled, setFindingsReconciled] = useState(false);
  const [verificationNotes, setVerificationNotes] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");

  const importsQuery = useInfiniteQuery({
    queryKey: ["audit-report-imports"],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => auditApi.listAuditReportImports({ limit: IMPORT_FETCH_LIMIT, offset: pageParam }),
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length > IMPORT_PAGE_SIZE ? allPages.length * IMPORT_PAGE_SIZE : undefined,
    enabled: canReadQueue,
  });
  const selectedImportQuery = useQuery({
    queryKey: ["audit-report-imports", selectedImportId],
    queryFn: () => auditApi.getAuditReportImport(selectedImportId),
    enabled: canReadQueue && Boolean(selectedImportId),
  });

  const stageMutation = useMutation({
    mutationFn: (payload: AuditReportImportCreate) => auditApi.createAuditReportImport(payload),
    onSuccess: async (candidate: AuditReportImport) => {
      await queryClient.invalidateQueries({ queryKey: ["audit-report-imports"] });
      setStageForm(EMPTY_STAGE_FORM);
      setFindingsJson("[]");
      setShowStageForm(false);
      setStageError("");
      setActionError("");
      setActionMessage(`Candidate ${candidate.audit_number} staged for independent review. No report or findings have been created.`);
    },
    onError: () => setStageError("Unable to stage the audit candidate. Check the source PDF path, checksum, identities, and findings."),
  });

  const verifyMutation = useMutation({
    mutationFn: ({ importId, payload }: { importId: string; payload: AuditReportImportReview }) =>
      auditApi.verifyAuditReportImport(importId, payload),
    onSuccess: async (result: { audit_number: string }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["audit-report-imports"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-reports"] }),
      ]);
      setSelectedImportId("");
      resetReviewForm();
      setActionError("");
      setActionMessage(`Candidate ${result.audit_number} was verified; the report and findings are now available.`);
    },
    onError: () => setActionError("Verification was not completed. Refresh the candidate and re-check the source before retrying."),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ importId, reason }: { importId: string; reason: string }) =>
      auditApi.rejectAuditReportImport(importId, reason),
    onSuccess: async (result: { import_id: string }) => {
      await queryClient.invalidateQueries({ queryKey: ["audit-report-imports"] });
      setSelectedImportId("");
      resetReviewForm();
      setActionError("");
      setActionMessage(`Candidate ${result.import_id} was rejected. No report or findings were created.`);
    },
    onError: () => setActionError("The candidate was not rejected. Refresh its status and try again."),
  });

  function resetReviewForm() {
    setSourceChecksumConfirmed(false);
    setFindingsReconciled(false);
    setVerificationNotes("");
    setRejectionReason("");
  }

  function updateStageField(field: keyof StageFormFields, value: string) {
    setStageForm((current) => ({ ...current, [field]: value }));
  }

  function handleStageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStageError("");
    setActionError("");
    setActionMessage("");
    let findings: AuditReportImportFindingInput[];
    try {
      const parsed: unknown = JSON.parse(findingsJson);
      if (!Array.isArray(parsed) || parsed.length === 0) throw new Error("Expected a non-empty findings array");
      findings = parsed as AuditReportImportFindingInput[];
    } catch {
      setStageError("Findings JSON must be a valid, non-empty array.");
      return;
    }
    stageMutation.mutate({
      ...stageForm,
      scope: stageForm.scope || undefined,
      regulatory_basis: stageForm.regulatory_basis || undefined,
      findings,
    });
  }

  function openImport(importId: string) {
    setActionError("");
    setActionMessage("");
    resetReviewForm();
    setSelectedImportId((current) => current === importId ? "" : importId);
  }

  function handleVerify(event: FormEvent<HTMLFormElement>, candidate: AuditReportImport) {
    event.preventDefault();
    if (!sourceChecksumConfirmed || !findingsReconciled || verificationNotes.trim().length < 20) return;
    setActionError("");
    setActionMessage("");
    verifyMutation.mutate({
      importId: candidate.import_id,
      payload: {
        source_checksum_confirmed: true,
        findings_reconciled: true,
        verification_notes: verificationNotes.trim(),
      },
    });
  }

  function handleReject(event: FormEvent<HTMLFormElement>, candidate: AuditReportImport) {
    event.preventDefault();
    if (rejectionReason.trim().length < 10) return;
    setActionError("");
    setActionMessage("");
    rejectMutation.mutate({ importId: candidate.import_id, reason: rejectionReason.trim() });
  }

  if (!canReadQueue) return null;

  const selectedImport = selectedImportQuery.data;
  const importCandidates = (importsQuery.data?.pages ?? []).flatMap((page) => page.slice(0, IMPORT_PAGE_SIZE));

  return (
    <section className="app-surface mt-5 space-y-4 p-5" aria-labelledby="audit-provenance-title">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="app-label mb-1">Controlled historical records</div>
          <h2 id="audit-provenance-title" className="text-lg font-bold text-kfl-text">Historical Audit Provenance</h2>
          <p className="mt-1 max-w-3xl text-sm text-kfl-muted">
            Staging a candidate does not create a report. Only an independent provenance review can publish the report and findings.
          </p>
        </div>
        {canImport && (
          <button
            type="button"
            onClick={() => { setShowStageForm((open) => !open); setStageError(""); setActionMessage(""); }}
            className="app-btn-primary shrink-0"
            aria-expanded={showStageForm}
            aria-controls="audit-import-stage-form"
          >
            {showStageForm ? "Cancel Staging" : "Stage Historical Import"}
          </button>
        )}
      </header>

      <p role="note" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        The source PDF must already be retained under the controlled attachments directory. This screen does not upload files or change accounts and roles.
      </p>

      {actionMessage && <p role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{actionMessage}</p>}
      {actionError && <p role="alert" className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{actionError}</p>}

      {canImport && showStageForm && (
        <form id="audit-import-stage-form" onSubmit={handleStageSubmit} className="space-y-4 rounded border border-kfl-border p-4">
          <div>
            <h3 className="font-semibold text-kfl-text">Stage import candidate</h3>
            <p className="mt-1 text-xs text-kfl-muted">Keep the source auditor's exact ID and name. The verifier and importer must be separate from the source auditor and auditee.</p>
          </div>
          {stageError && <p role="alert" className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{stageError}</p>}
          <div className="grid gap-3 md:grid-cols-2">
            <FormField htmlFor="import-audit-number" label="Import Audit Number" required>
              <input id="import-audit-number" name="audit_number" className="app-input" value={stageForm.audit_number} onChange={(event) => updateStageField("audit_number", event.target.value)} required />
            </FormField>
            <FormField htmlFor="import-audit-date" label="Import Audit Date" required>
              <input id="import-audit-date" name="audit_date" type="date" className="app-input" value={stageForm.audit_date} onChange={(event) => updateStageField("audit_date", event.target.value)} required />
            </FormField>
            <FormField htmlFor="source-auditor-id" label="Source Auditor ID" hint="Enter the source ID literally; do not replace it with the verifier." required>
              <input id="source-auditor-id" name="source_auditor_id" className="app-input" value={stageForm.source_auditor_id} onChange={(event) => updateStageField("source_auditor_id", event.target.value)} autoComplete="off" required />
            </FormField>
            <FormField htmlFor="source-auditor-name" label="Source Auditor Name" required>
              <input id="source-auditor-name" name="source_auditor_name" className="app-input" value={stageForm.source_auditor_name} onChange={(event) => updateStageField("source_auditor_name", event.target.value)} required />
            </FormField>
            <FormField htmlFor="import-auditee-id" label="Import Auditee ID" required>
              <input id="import-auditee-id" name="auditee_id" className="app-input" value={stageForm.auditee_id} onChange={(event) => updateStageField("auditee_id", event.target.value)} autoComplete="off" required />
            </FormField>
            <FormField htmlFor="import-scope" label="Import Scope">
              <input id="import-scope" name="scope" className="app-input" value={stageForm.scope} onChange={(event) => updateStageField("scope", event.target.value)} />
            </FormField>
            <FormField htmlFor="import-regulatory-basis" label="Import Regulatory Basis">
              <input id="import-regulatory-basis" name="regulatory_basis" className="app-input" value={stageForm.regulatory_basis} onChange={(event) => updateStageField("regulatory_basis", event.target.value)} />
            </FormField>
            <FormField htmlFor="import-evidence-file" label="Existing Source PDF Path" hint="Relative path under attachments/; this form does not upload the PDF." required>
              <input id="import-evidence-file" name="evidence_file" className="app-input" placeholder="attachments/source-report.pdf" value={stageForm.evidence_file} onChange={(event) => updateStageField("evidence_file", event.target.value)} required />
            </FormField>
            <FormField htmlFor="import-evidence-sha256" label="Expected Source SHA-256" hint="64 lowercase hexadecimal characters." required>
              <input id="import-evidence-sha256" name="expected_evidence_sha256" className="app-input font-mono" pattern="[0-9a-f]{64}" maxLength={64} value={stageForm.expected_evidence_sha256} onChange={(event) => updateStageField("expected_evidence_sha256", event.target.value)} required />
            </FormField>
          </div>
          <FormField htmlFor="import-findings-json" label="Findings JSON" hint="Paste a non-empty JSON array with one object per finding. The server validates every field." required>
            <textarea id="import-findings-json" name="findings" className="app-input min-h-48 font-mono text-xs" value={findingsJson} onChange={(event) => setFindingsJson(event.target.value)} spellCheck={false} required />
          </FormField>
          <button type="submit" className="app-btn-primary w-full disabled:opacity-60" disabled={stageMutation.isPending}>
            {stageMutation.isPending ? "Staging candidate…" : "Stage Candidate"}
          </button>
        </form>
      )}

      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-semibold text-kfl-text">Import review queue</h3>
          <button type="button" onClick={() => void importsQuery.refetch()} className="app-btn-secondary">Refresh queue</button>
        </div>
        {importsQuery.isError && !importsQuery.data ? (
          <div role="alert" className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            Unable to load audit import candidates. <button type="button" className="underline" onClick={() => void importsQuery.refetch()}>Retry</button>
          </div>
        ) : importsQuery.isLoading ? (
          <p role="status" className="text-sm text-kfl-muted">Loading audit import candidates…</p>
        ) : importCandidates.length === 0 ? (
          <p className="rounded border border-dashed border-kfl-border p-4 text-sm text-kfl-muted">No audit import candidates.</p>
        ) : (
          <ul className="divide-y divide-kfl-border rounded border border-kfl-border">
            {importCandidates.map((candidate) => (
              <li key={candidate.import_id} className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-kfl-text">{candidate.audit_number}</span>
                    <span className={`app-status ${candidate.status === "imported" ? "app-status-healthy" : "app-status-warning"}`}>
                      {candidate.status.replace(/_/g, " ").toUpperCase()}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-kfl-muted">Source: {candidate.source_auditor_name} ({candidate.source_auditor_id}) · Imported by {candidate.imported_by}</p>
                </div>
                <button type="button" className="app-btn-secondary shrink-0" onClick={() => openImport(candidate.import_id)} aria-expanded={selectedImportId === candidate.import_id}>
                  {selectedImportId === candidate.import_id ? "Close import details" : `View import ${candidate.audit_number}`}
                </button>
              </li>
            ))}
          </ul>
        )}
        {importsQuery.isFetchNextPageError && (
          <p role="alert" className="text-sm text-rose-800">
            Unable to load more candidates. <button type="button" className="underline" onClick={() => void importsQuery.fetchNextPage()}>Retry</button>
          </p>
        )}
        {importsQuery.hasNextPage && (
          <button
            type="button"
            onClick={() => void importsQuery.fetchNextPage()}
            className="app-btn-secondary w-full"
            disabled={importsQuery.isFetchingNextPage}
          >
            {importsQuery.isFetchingNextPage ? "Loading more candidates…" : "Load more candidates"}
          </button>
        )}
      </div>

      {selectedImportId && (
        <div className="space-y-4 rounded border border-kfl-border p-4">
          {selectedImportQuery.isError ? (
            <p role="alert" className="text-sm text-rose-800">Unable to load this import candidate.</p>
          ) : selectedImportQuery.isLoading || !selectedImport ? (
            <p role="status" className="text-sm text-kfl-muted">Loading import details…</p>
          ) : (
            <ImportCandidateReview
              candidate={selectedImport}
              canVerify={canVerify}
              sourceChecksumConfirmed={sourceChecksumConfirmed}
              setSourceChecksumConfirmed={setSourceChecksumConfirmed}
              findingsReconciled={findingsReconciled}
              setFindingsReconciled={setFindingsReconciled}
              verificationNotes={verificationNotes}
              setVerificationNotes={setVerificationNotes}
              rejectionReason={rejectionReason}
              setRejectionReason={setRejectionReason}
              verifying={verifyMutation.isPending}
              rejecting={rejectMutation.isPending}
              onVerify={(event) => handleVerify(event, selectedImport)}
              onReject={(event) => handleReject(event, selectedImport)}
            />
          )}
        </div>
      )}
    </section>
  );
}

function ImportCandidateReview({
  candidate,
  canVerify,
  sourceChecksumConfirmed,
  setSourceChecksumConfirmed,
  findingsReconciled,
  setFindingsReconciled,
  verificationNotes,
  setVerificationNotes,
  rejectionReason,
  setRejectionReason,
  verifying,
  rejecting,
  onVerify,
  onReject,
}: {
  candidate: AuditReportImport;
  canVerify: boolean;
  sourceChecksumConfirmed: boolean;
  setSourceChecksumConfirmed: (value: boolean) => void;
  findingsReconciled: boolean;
  setFindingsReconciled: (value: boolean) => void;
  verificationNotes: string;
  setVerificationNotes: (value: string) => void;
  rejectionReason: string;
  setRejectionReason: (value: string) => void;
  verifying: boolean;
  rejecting: boolean;
  onVerify: (event: FormEvent<HTMLFormElement>) => void;
  onReject: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="space-y-4" aria-labelledby={`import-detail-${candidate.import_id}`}>
      <div>
        <h3 id={`import-detail-${candidate.import_id}`} className="font-semibold text-kfl-text">Review {candidate.audit_number}</h3>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="font-semibold text-kfl-muted">Source auditor</dt><dd>{candidate.source_auditor_name} ({candidate.source_auditor_id})</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Auditee</dt><dd>{candidate.auditee_id}</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Audit date</dt><dd>{candidate.audit_date}</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Scope</dt><dd>{candidate.scope || "—"}</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Regulatory basis</dt><dd>{candidate.regulatory_basis || "—"}</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Import operator</dt><dd>{candidate.imported_by}</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Status</dt><dd>{candidate.status.replace(/_/g, " ")}</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Source PDF SHA-256</dt><dd className="break-all font-mono text-xs">{candidate.evidence_sha256}</dd></div>
          <div><dt className="font-semibold text-kfl-muted">Payload SHA-256</dt><dd className="break-all font-mono text-xs">{candidate.payload_sha256}</dd></div>
        </dl>
        <a
          href={`/api/p3/audit-report-imports/${encodeURIComponent(candidate.import_id)}/evidence`}
          className="mt-3 inline-block text-sm text-kfl-blue underline"
          aria-label={`Download source PDF for ${candidate.audit_number}`}
        >
          Download hash-checked source PDF
        </a>
      </div>

      <div className="overflow-x-auto rounded border border-kfl-border">
        <table className="min-w-full">
          <caption className="sr-only">Imported source findings for {candidate.audit_number}</caption>
          <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
            <tr>
              <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">Number</th>
              <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">Area / Level</th>
              <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">Finding</th>
              <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">Reference / Due</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-kfl-border">
            {(candidate.findings ?? []).map((finding, index) => (
              <tr key={`${finding.finding_number}-${index}`}>
                <td className="px-3 py-3 font-mono text-xs">{finding.finding_number}</td>
                <td className="px-3 py-3 text-xs">{finding.area} / {finding.level}</td>
                <td className="px-3 py-3 text-xs"><div className="font-semibold">{finding.title}</div><p className="mt-1 whitespace-pre-wrap">{finding.description}</p></td>
                <td className="px-3 py-3 text-xs"><div>{finding.regulatory_reference || "—"}</div><div className="mt-1">{finding.due_date || "—"}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canVerify && candidate.status === "pending_verification" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <form onSubmit={onVerify} className="space-y-3 rounded border border-kfl-border p-4">
            <h4 className="font-semibold text-kfl-text">Verify provenance</h4>
            <label htmlFor={`source-check-${candidate.import_id}`} className="flex items-start gap-2 text-sm">
              <input id={`source-check-${candidate.import_id}`} name="source_checksum_confirmed" type="checkbox" checked={sourceChecksumConfirmed} onChange={(event) => setSourceChecksumConfirmed(event.target.checked)} />
              <span>I confirmed the source PDF checksum against the controlled source.</span>
            </label>
            <label htmlFor={`findings-check-${candidate.import_id}`} className="flex items-start gap-2 text-sm">
              <input id={`findings-check-${candidate.import_id}`} name="findings_reconciled" type="checkbox" checked={findingsReconciled} onChange={(event) => setFindingsReconciled(event.target.checked)} />
              <span>I reconciled every finding against the source report.</span>
            </label>
            <FormField htmlFor={`verification-notes-${candidate.import_id}`} label="Verification Notes" hint="At least 20 characters explaining the review basis." required>
              <textarea id={`verification-notes-${candidate.import_id}`} name="verification_notes" className="app-input min-h-24" value={verificationNotes} onChange={(event) => setVerificationNotes(event.target.value)} minLength={20} required />
            </FormField>
            <button type="submit" className="app-btn-primary w-full disabled:opacity-60" disabled={verifying || !sourceChecksumConfirmed || !findingsReconciled || verificationNotes.trim().length < 20}>
              {verifying ? "Verifying…" : "Verify and Import"}
            </button>
          </form>
          <form onSubmit={onReject} className="space-y-3 rounded border border-kfl-border p-4">
            <h4 className="font-semibold text-kfl-text">Reject candidate</h4>
            <FormField htmlFor={`rejection-reason-${candidate.import_id}`} label="Rejection Reason" hint="At least 10 characters; no report or findings will be created." required>
              <textarea id={`rejection-reason-${candidate.import_id}`} name="rejection_reason" className="app-input min-h-24" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} minLength={10} required />
            </FormField>
            <button type="submit" className="app-btn-secondary w-full disabled:opacity-60" disabled={rejecting || rejectionReason.trim().length < 10}>
              {rejecting ? "Rejecting…" : "Reject Import"}
            </button>
          </form>
        </div>
      ) : candidate.status === "pending_verification" ? (
        <p role="note" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Only a distinct independent_auditor can verify or reject this candidate.
        </p>
      ) : (
        <p role="status" className="text-sm text-kfl-muted">
          {candidate.status === "imported" ? `Verified by ${candidate.verified_by ?? "—"}.` : `Rejected: ${candidate.verification_notes ?? "No reason recorded."}`}
        </p>
      )}
    </div>
  );
}
