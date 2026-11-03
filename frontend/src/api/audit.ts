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
  listAuditReports: (params?: Record<string, any>) =>
    api.get<AuditReport[]>("/p3/audit-reports", { params }).then((r: any) => r.data),
  createAuditReport: (data: any) =>
    api.post<AuditReport>("/p3/audit-reports", data).then((r: any) => r.data),

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
