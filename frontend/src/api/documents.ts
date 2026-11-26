import type { Document } from "../types";
import api from "./client";

export interface DocumentPage {
  data: Document[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentListParams {
  status?: string;
  doc_class?: string;
  document_category?: string;
  limit?: number;
  offset?: number;
}

export async function listDocuments(params?: DocumentListParams): Promise<DocumentPage> {
  const response = params
    ? await api.get<DocumentPage>("/p0/documents", { params })
    : await api.get<DocumentPage>("/p0/documents");
  return response.data;
}
