import api from "./client";
import { OutsourcedFunction, SafetyKPI, SecurityReview, DGResponsibilityMatrix } from "../types";

export const p2Api = {
  // Outsourced Functions (QMS-06)
  listOutsourcedFunctions: (params?: Record<string, any>) =>
    api.get<OutsourcedFunction[]>("/p1/outsourced-functions", { params }).then((r: any) => r.data),
  createOutsourcedFunction: (data: any) =>
    api.post<OutsourcedFunction>("/p1/outsourced-functions", data).then((r: any) => r.data),
  updateOutsourcedFunction: (id: string, data: any) =>
    api.patch<OutsourcedFunction>(`/p1/outsourced-functions/${id}`, data).then((r: any) => r.data),

  // Safety KPIs (SAF-08)
  listSafetyKPIs: (params?: Record<string, any>) =>
    api.get<SafetyKPI[]>("/p1/safety-kpis", { params }).then((r: any) => r.data),
  createSafetyKPI: (data: any) =>
    api.post<SafetyKPI>("/p1/safety-kpis", data).then((r: any) => r.data),
  updateSafetyKPI: (id: string, data: any) =>
    api.patch<SafetyKPI>(`/p1/safety-kpis/${id}`, data).then((r: any) => r.data),

  // Security Reviews (SEC-06)
  listSecurityReviews: (params?: Record<string, any>) =>
    api.get<SecurityReview[]>("/p1/security-reviews", { params }).then((r: any) => r.data),
  createSecurityReview: (data: any) =>
    api.post<SecurityReview>("/p1/security-reviews", data).then((r: any) => r.data),
  updateSecurityReview: (id: string, data: any) =>
    api.patch<SecurityReview>(`/p1/security-reviews/${id}`, data).then((r: any) => r.data),

  // DG Responsibility Matrix (DG-12)
  listDGMatrix: (params?: Record<string, any>) =>
    api.get<DGResponsibilityMatrix[]>("/p1/dg-responsibility-matrix", { params }).then((r: any) => r.data),
  createDGMatrix: (data: any) =>
    api.post<DGResponsibilityMatrix>("/p1/dg-responsibility-matrix", data).then((r: any) => r.data),
  updateDGMatrix: (id: string, data: any) =>
    api.patch<DGResponsibilityMatrix>(`/p1/dg-responsibility-matrix/${id}`, data).then((r: any) => r.data),

  // Document Distributions (DOC-15)
  listDistributions: (params?: Record<string, any>) =>
    api.get<any[]>("/p0/distributions", { params }).then((r: any) => r.data),
  createDistribution: (data: any) =>
    api.post<any>("/p0/distributions", data).then((r: any) => r.data),
  acknowledgeDistribution: (id: string) =>
    api.post(`/p0/distributions/${id}/acknowledge`).then((r: any) => r.data),

  // Document Ingestion (Phase 3)
  ingestDocument: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post<{ document_type: string; confidence: number; extracted_fields: Record<string, any>; target_table: string; raw_text_preview: string }>("/p2/ingest/document", formData).then((r: any) => r.data);
  },
  applyIngestion: (data: {
    document_type: string;
    target_table: string;
    extracted_fields: Record<string, any>;
    aircraft_id?: string;
    person_id?: string;
    document_id?: string;
  }) =>
    api.post<any>("/p2/ingest/document/apply", data).then((r: any) => r.data),

  // Document bulk intake (P0 /documents/ingest/bulk) — historical records.
  bulkIngestDocument: (files: File[]) => {
    const formData = new FormData();
    for (const file of files) formData.append("file", file);
    return api.post<{
      batch_id: string;
      items: Array<{
        staging_id: string;
        file_name: string;
        document_type: string;
        confidence: number;
        target_table: string;
        status: string;
        extracted_fields: Record<string, any>;
        raw_text_preview: string;
        duplicate_of?: string;
      }>;
      staged: number;
      duplicates: number;
      rejected: number;
    }>("/p0/documents/ingest/bulk", formData).then((r: any) => r.data);
  },
  applyBulkIngestionDocument: (data: {
    items: Array<{
      staging_id: string;
      target_table: string;
      document_id?: string;
      aircraft_id?: string;
      person_id?: string;
      // audit_report_import provenance fields
      source_auditor_id?: string;
      source_auditor_name?: string;
      auditee_id?: string;
      audit_number?: string;
      audit_date?: string;
      scope?: string;
      regulatory_basis?: string;
    }>;
  }) =>
    api.post<any>("/p0/documents/ingest/bulk/apply", data).then((r: any) => r.data),

  // ==================== P2: Document Proposals ====================
  createProposal: (docId: string, body: any) =>
    api.post<any>(`/p2/documents/${docId}/proposals`, body).then((r: any) => r.data),
  listProposals: (docId: string, params?: Record<string, any>) =>
    api.get<any[]>(`/p2/documents/${docId}/proposals`, { params }).then((r: any) => r.data),
  getProposal: (proposalId: string) =>
    api.get<any>(`/p2/proposals/${proposalId}`).then((r: any) => r.data),
  updateProposal: (proposalId: string, body: any) =>
    api.patch<any>(`/p2/proposals/${proposalId}`, body).then((r: any) => r.data),
  deleteProposal: (proposalId: string) =>
    api.delete<any>(`/p2/proposals/${proposalId}`).then((r: any) => r.data),
  previewProposals: (docId: string, proposedContent: string) =>
    api.post<{ document_id: string; base_version_id: string; changes: any[]; change_count: number }>(
      `/p2/documents/${docId}/proposals/preview`,
      { proposed_content: proposedContent },
    ).then((r: any) => r.data),
  createProposalBatch: (docId: string, proposedContent: string, body?: any) =>
    api.post<{ document_id: string; base_version_id: string; change_set_id: string; proposals: any[]; created_count: number }>(
      `/p2/documents/${docId}/proposals/batch`,
      { proposed_content: proposedContent, ...body },
    ).then((r: any) => r.data),
  applyProposal: (proposalId: string) =>
    api.post<any>(`/p2/proposals/${proposalId}/apply`).then((r: any) => r.data),

  // ==================== P2: Document Annotations ====================
  createAnnotation: (docId: string, body: any) =>
    api.post<any>(`/p2/documents/${docId}/annotations`, body).then((r: any) => r.data),
  listAnnotations: (docId: string, status?: string) =>
    api.get<any[]>(`/p2/documents/${docId}/annotations`, { params: status ? { status } : undefined }).then((r: any) => r.data),
  updateAnnotation: (annotationId: string, body: any) =>
    api.patch<any>(`/p2/annotations/${annotationId}`, body).then((r: any) => r.data),
  deleteAnnotation: (annotationId: string) =>
    api.delete<any>(`/p2/annotations/${annotationId}`).then((r: any) => r.data),

  // ==================== P2: Personnel Licenses ====================
  createLicense: (body: any) =>
    api.post<any>("/p2/personnel/licenses", body).then((r: any) => r.data),
  listLicenses: (params?: Record<string, any>) =>
    api.get<any[]>("/p2/personnel/licenses", { params }).then((r: any) => r.data),
  getLicense: (licenseId: string) =>
    api.get<any>(`/p2/personnel/licenses/${licenseId}`).then((r: any) => r.data),
  updateLicense: (licenseId: string, body: any) =>
    api.patch<any>(`/p2/personnel/licenses/${licenseId}`, body).then((r: any) => r.data),
  deleteLicense: (licenseId: string) =>
    api.delete<any>(`/p2/personnel/licenses/${licenseId}`).then((r: any) => r.data),
  listExpiringLicenses: (days = 30) =>
    api.get<any[]>(`/p2/personnel/expiring-licenses?days=${days}`).then((r: any) => r.data),

  // ==================== P2: Aircraft Insurance ====================
  createAircraftInsurance: (aircraftId: string, body: any) =>
    api.post<any>(`/p2/aircraft/${aircraftId}/insurance`, body).then((r: any) => r.data),
  listAircraftInsurance: (aircraftId: string) =>
    api.get<any[]>(`/p2/aircraft/${aircraftId}/insurance`).then((r: any) => r.data),
  updateAircraftInsurance: (insuranceId: string, body: any) =>
    api.patch<any>(`/p2/insurance/${insuranceId}`, body).then((r: any) => r.data),
  listExpiringInsurance: () =>
    api.get<any[]>("/p2/insurance/expiring").then((r: any) => r.data),

  // ==================== P2: Aircraft Documents ====================
  createAircraftDocument: (aircraftId: string, body: any) =>
    api.post<any>(`/p2/aircraft/${aircraftId}/documents`, body).then((r: any) => r.data),
  listAircraftDocuments: (aircraftId: string, documentType?: string) =>
    api.get<any[]>(`/p2/aircraft/${aircraftId}/documents`, { params: documentType ? { document_type: documentType } : undefined }).then((r: any) => r.data),
  updateAircraftDocument: (docId: string, body: any) =>
    api.patch<any>(`/p2/aircraft-documents/${docId}`, body).then((r: any) => r.data),
  listExpiringAircraftDocuments: () =>
    api.get<any[]>("/p2/aircraft-documents/expiring").then((r: any) => r.data),
  deleteAircraftDocument: (docId: string) =>
    api.delete<any>(`/p2/aircraft-documents/${docId}`).then((r: any) => r.data),
};
