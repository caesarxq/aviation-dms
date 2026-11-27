import type { Document } from "../types";
import api from "./client";

export interface Folder {
  folder_id: string;
  name: string;
  description: string | null;
  color: string | null;
  document_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

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
  folder_id?: string | null;
  limit?: number;
  offset?: number;
}

export interface PaginatedFolderResponse {
  data: Folder[];
  total: number;
  limit: number;
  offset: number;
}

export async function listDocuments(params?: DocumentListParams): Promise<DocumentPage> {
  const response = params
    ? await api.get<DocumentPage>("/p0/documents", { params })
    : await api.get<DocumentPage>("/p0/documents");
  return response.data;
}

export async function listFolders(params?: { limit?: number; offset?: number }): Promise<PaginatedFolderResponse> {
  const response = await api.get<PaginatedFolderResponse>("/p0/folders", { params });
  return response.data;
}

export async function createFolder(data: { name: string; description?: string; color?: string }): Promise<Folder> {
  const response = await api.post<Folder>("/p0/folders", data);
  return response.data;
}

export async function updateFolder(folderId: string, data: { name?: string; description?: string; color?: string }): Promise<Folder> {
  const response = await api.patch<Folder>(`/p0/folders/${folderId}`, data);
  return response.data;
}

export async function deleteFolder(folderId: string): Promise<void> {
  await api.delete(`/p0/folders/${folderId}`);
}

export async function moveDocumentToFolder(documentId: string, folderId: string | null): Promise<Document> {
  const response = await api.patch<Document>(`/p0/documents/${documentId}`, { folder_id: folderId });
  return response.data;
}
