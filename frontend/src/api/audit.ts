import api from "./client";

export interface AuditReport {
  audit_id: string;
  audit_number: string;
  audit_date: string;
  auditor_id: string;
  auditee_id: string;
  scope: string | null;
  regulatory_basis: string | null;
  status: string;
  evidence_file: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AuditReportListParams {
  status?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface AuditFinding {
  finding_id: string;
  audit_id: string;
  finding_number: string;
  area: string;
  level: number;
  title: string;
  description: string | null;
  regulatory_reference: string | null;
  status: string;
  corrective_action_id: string | null;
  due_date: string | null;
  closed_at: string | null;
  closed_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export type AuditFindingStatus = "open" | "in_progress" | "closed";

export type AuditReportImportStatus = "pending_verification" | "imported" | "rejected";

export interface AuditReportImportFinding {
  finding_number: string;
  area: string;
  level: number;
  title: string;
  description: string;
  regulatory_reference: string | null;
  due_date: string | null;
}

export interface AuditReportImportFindingInput {
  finding_number: string;
  area: string;
  level: number;
  title: string;
  description: string;
  regulatory_reference?: string | null;
  due_date?: string | null;
}

export interface AuditReportImport {
  import_id: string;
  audit_number: string;
  audit_date: string;
  source_auditor_id: string;
  source_auditor_name: string;
  auditee_id: string;
  scope: string | null;
  regulatory_basis: string | null;
  evidence_sha256: string;
  payload_sha256: string;
  evidence_download_url: string;
  imported_by: string;
  created_at: string;
  status: AuditReportImportStatus;
  verified_by: string | null;
  verified_at: string | null;
  verification_notes: string | null;
  audit_id: string | null;
  findings?: AuditReportImportFinding[];
}

export interface AuditReportImportCreate {
  audit_number: string;
  audit_date: string;
  source_auditor_id: string;
  source_auditor_name: string;
  auditee_id: string;
  scope?: string;
  regulatory_basis?: string;
  evidence_file: string;
  expected_evidence_sha256: string;
  findings: AuditReportImportFindingInput[];
}

export interface AuditReportImportReview {
  source_checksum_confirmed: boolean;
  findings_reconciled: boolean;
  verification_notes: string;
}

export interface AuditReportImportVerificationResult {
  import_id: string;
  audit_id: string;
  audit_number: string;
  source_auditor_id: string;
  source_auditor_name: string;
  imported_by: string;
  verified_by: string;
  verified_at: string;
  status: "imported";
}

export interface AuditReportImportRejectionResult {
  import_id: string;
  status: "rejected";
  rejected_by: string;
  rejected_at: string;
}

export interface AuditFindingListParams {
  audit_id?: string;
  status?: AuditFindingStatus;
  level?: number;
  area?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export const auditApi = {
  listAuditReports: (params?: AuditReportListParams) =>
    api.get<AuditReport[]>("/p3/audit-reports", { params }).then((r: any) => r.data),
  createAuditReport: (data: any) =>
    api.post<AuditReport>("/p3/audit-reports", data).then((r: any) => r.data),

  listAuditReportImports: (params?: { status?: AuditReportImportStatus; limit?: number; offset?: number }): Promise<AuditReportImport[]> =>
    api.get<AuditReportImport[]>("/p3/audit-report-imports", { params }).then((response) => response.data),
  getAuditReportImport: (id: string): Promise<AuditReportImport> =>
    api.get<AuditReportImport>(`/p3/audit-report-imports/${encodeURIComponent(id)}`).then((response) => response.data),
  createAuditReportImport: (data: AuditReportImportCreate): Promise<AuditReportImport> =>
    api.post<AuditReportImport>("/p3/audit-report-imports", data).then((response) => response.data),
  verifyAuditReportImport: (id: string, data: AuditReportImportReview): Promise<AuditReportImportVerificationResult> =>
    api.post<AuditReportImportVerificationResult>(`/p3/audit-report-imports/${encodeURIComponent(id)}/verify`, data).then((response) => response.data),
  rejectAuditReportImport: (id: string, reason: string): Promise<AuditReportImportRejectionResult> =>
    api.post<AuditReportImportRejectionResult>(`/p3/audit-report-imports/${encodeURIComponent(id)}/reject`, { reason }).then((response) => response.data),

  listAuditFindings: (params?: AuditFindingListParams) =>
    api.get<AuditFinding[]>("/p3/audit-findings", { params }).then((r: any) => r.data),
  getAuditFinding: (id: string) =>
    api.get<AuditFinding>(`/p3/audit-findings/${encodeURIComponent(id)}`).then((r: any) => r.data),
  createAuditFinding: (data: any) =>
    api.post<AuditFinding>("/p3/audit-findings", data).then((r: any) => r.data),
  updateAuditFinding: (id: string, data: any) =>
    api.patch<AuditFinding>(`/p3/audit-findings/${id}`, data).then((r: any) => r.data),
  linkCorrectiveAction: (id: string, data: any) =>
    api.post(`/p3/audit-findings/${id}/car`, data).then((r: any) => r.data),

  getAuditFindingsSummary: () =>
    api.get<any>("/p3/audit-findings/summary").then((r: any) => r.data),
};
