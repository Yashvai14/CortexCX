import apiClient from './client';
import type {
  KnowledgeSource,
  KnowledgeDocument,
  DocumentChunk,
  KnowledgeSearchResponse,
} from '@/types';

// ── Knowledge Sources ──────────────────────────────────────────────
export async function listKnowledgeSources(): Promise<KnowledgeSource[]> {
  const resp = await apiClient.get<KnowledgeSource[]>('/knowledge/sources');
  return resp.data;
}

export async function createKnowledgeSource(data: {
  name: string;
  source_type?: string;
  source_url?: string;
}): Promise<KnowledgeSource> {
  const resp = await apiClient.post<KnowledgeSource>('/knowledge/sources', data);
  return resp.data;
}

export async function getKnowledgeSource(id: string): Promise<KnowledgeSource> {
  const resp = await apiClient.get<KnowledgeSource>(`/knowledge/sources/${id}`);
  return resp.data;
}

// ── Documents ─────────────────────────────────────────────────────
export async function listDocuments(knowledgeSourceId?: string): Promise<KnowledgeDocument[]> {
  const resp = await apiClient.get<KnowledgeDocument[]>('/knowledge/documents', {
    params: knowledgeSourceId ? { knowledge_source_id: knowledgeSourceId } : undefined,
  });
  return resp.data;
}

export async function getDocument(id: string): Promise<KnowledgeDocument> {
  const resp = await apiClient.get<KnowledgeDocument>(`/knowledge/documents/${id}`);
  return resp.data;
}

export async function createDocument(data: {
  knowledge_source_id: string;
  title: string;
  content?: string;
  filename?: string;
  metadata_json?: Record<string, unknown>;
}): Promise<KnowledgeDocument> {
  const resp = await apiClient.post<KnowledgeDocument>('/knowledge/documents', data);
  return resp.data;
}

export async function listDocumentChunks(documentId: string): Promise<DocumentChunk[]> {
  const resp = await apiClient.get<DocumentChunk[]>(
    `/knowledge/documents/${documentId}/chunks`
  );
  return resp.data;
}

export async function embedDocument(documentId: string): Promise<KnowledgeDocument> {
  const resp = await apiClient.post<KnowledgeDocument>(
    `/knowledge/documents/${documentId}/embed`
  );
  return resp.data;
}

// ── Search ────────────────────────────────────────────────────────
export async function searchKnowledge(data: {
  query: string;
  top_k?: number;
  knowledge_source_id?: string;
}): Promise<KnowledgeSearchResponse> {
  const resp = await apiClient.post<KnowledgeSearchResponse>('/knowledge/search', data);
  return resp.data;
}

// ── Upload / URL / maintenance ────────────────────────────────────
export async function uploadDocument(
  file: File,
  knowledgeSourceId: string,
  title?: string,
): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append('file', file);
  form.append('knowledge_source_id', knowledgeSourceId);
  if (title) form.append('title', title);
  const resp = await apiClient.post<KnowledgeDocument>('/knowledge/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return resp.data;
}

export async function ingestUrl(
  knowledgeSourceId: string,
  url: string,
  title?: string,
): Promise<KnowledgeDocument> {
  const resp = await apiClient.post<KnowledgeDocument>('/knowledge/url', {
    knowledge_source_id: knowledgeSourceId,
    url,
    title: title || undefined,
  });
  return resp.data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/knowledge/documents/${documentId}`);
}

export async function reindexKnowledge(): Promise<{ message: string; documents: number }> {
  const resp = await apiClient.post<{ message: string; documents: number }>('/knowledge/reindex');
  return resp.data;
}
