import api from "./client";

export interface DocumentSection {
  section_id: string;
  document_id: string;
  version_id: string;
  section_number: string | null;
  heading: string;
  content_start_offset: number | null;
  content_end_offset: number | null;
  parent_section_id: string | null;
  sort_order: number;
  created_at: string;
}

export interface SectionExtractRequest {
  section_id: string;
  reason?: string;
}

export interface SectionExtractResponse {
  request_id: string;
  document_id: string;
  document_version_id: string;
  section_id: string;
  status: string;
  approval_required: boolean;
  created_at: string;
}

export interface ExtractionRequest {
  id: string;
  document_id: string;
  document_version_id: string;
  requested_by: string;
  section_id: string | null;
  reason: string;
  status: string;
  reviewed_by: string | null;
  review_comment: string | null;
  reviewed_at: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface HeadingBasedExtractRequest {
  heading: string;
  reason?: string;
}

export interface HeadingBasedExtractResponse {
  extraction_id: string;
  document_id: string;
  section_id: string | null;
  pages_extracted: number[];
  watermark_applied: boolean;
  download_url: string;
  created_at: string;
}

export interface DocumentClassification {
  code: string;
  name: string;
  requires_watermark: boolean;
  allow_full_download: boolean;
  requires_approval: boolean;
}

export interface DocumentClassificationRequest {
  classification_code: string;
}

export interface DocumentClassificationResponse {
  document_id: string;
  classification_code: string;
  name: string;
  requires_watermark: boolean;
  allow_full_download: boolean;
  requires_approval: boolean;
}

export interface DocumentPermissionGrant {
  role_id: string;
  permission_code: string;
  scope_section_id: string | null;
  valid_from?: string;
  valid_until?: string;
}

export interface DocumentPermission {
  id: string;
  document_id: string;
  role_id: string;
  permission_code: string;
  scope_section_id: string | null;
  valid_from: string;
  valid_until: string | null;
  created_by: string;
  created_at: string;
}

export const controlledDocumentApi = {
  // --- Sections ---
  listDocumentSections: (docId: string) =>
    api.get<DocumentSection[]>(`/p0/documents/${encodeURIComponent(docId)}/sections`).then((r) => r.data),

  getDocumentSection: (docId: string, sectionId: string) =>
    api.get<DocumentSection>(`/p0/documents/${encodeURIComponent(docId)}/sections/${encodeURIComponent(sectionId)}`).then((r) => r.data),

  // --- Section Extraction (page-range) ---
  requestSectionExtraction: (docId: string, sectionId: string, body: SectionExtractRequest) =>
    api.post<SectionExtractResponse>(`/p0/documents/${encodeURIComponent(docId)}/sections/${encodeURIComponent(sectionId)}/extract`, body).then((r) => r.data),

  listExtractionRequests: (params?: { status?: string; limit?: number; offset?: number }) =>
    api.get<ExtractionRequest[]>("/p0/extraction-requests", { params }).then((r) => r.data),

  getExtractionRequest: (requestId: string) =>
    api.get<ExtractionRequest>(`/p0/extraction-requests/${encodeURIComponent(requestId)}`).then((r) => r.data),

  downloadSectionExtraction: (extractionId: string) =>
    api.get(`/p0/extractions/${encodeURIComponent(extractionId)}/download`, { responseType: "blob" }),

  // --- Heading-Based Extraction ---
  extractByHeading: (docId: string, body: HeadingBasedExtractRequest) =>
    api.post<HeadingBasedExtractResponse>(`/p0/documents/${encodeURIComponent(docId)}/sections/extract-heading`, body).then((r) => r.data),

  // --- Extraction Approval (Admin) ---
  listPendingExtractionApprovals: () =>
    api.get<ExtractionRequest[]>("/p0/admin/extraction-requests").then((r) => r.data),

  approveExtractionRequest: (requestId: string) =>
    api.post<{ status: string; request_id: string }>(`/p0/admin/extraction-requests/${encodeURIComponent(requestId)}/approve`).then((r) => r.data),

  rejectExtractionRequest: (requestId: string) =>
    api.post<{ status: string; request_id: string }>(`/p0/admin/extraction-requests/${encodeURIComponent(requestId)}/reject`).then((r) => r.data),

  // --- Document Classification ---
  listDocumentClassifications: () =>
    api.get<DocumentClassification[]>("/p0/document-classifications").then((r) => r.data),

  classifyDocument: (docId: string, body: DocumentClassificationRequest) =>
    api.post<DocumentClassificationResponse>(`/p0/admin/documents/${encodeURIComponent(docId)}/classify`, body).then((r) => r.data),

  // --- Document Permissions ---
  listDocumentPermissions: (docId: string) =>
    api.get<DocumentPermission[]>(`/p0/admin/documents/${encodeURIComponent(docId)}/permissions`).then((r) => r.data),

  setDocumentPermissions: (docId: string, grants: DocumentPermissionGrant[]) =>
    api.put<DocumentPermission[]>(`/p0/admin/documents/${encodeURIComponent(docId)}/permissions`, grants).then((r) => r.data),
};
