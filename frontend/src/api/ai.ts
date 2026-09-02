import apiClient from './client';
import type {
  AIProcessConversationResponse,
  AIConversationStatusResponse,
  RAGProcessResponse,
} from '@/types';

export async function processConversationAI(
  conversationId: string,
  promptOverride?: string
): Promise<AIProcessConversationResponse> {
  const resp = await apiClient.post<AIProcessConversationResponse>(
    `/ai/conversations/${conversationId}/process`,
    promptOverride ? { prompt_override: promptOverride } : {}
  );
  return resp.data;
}

export async function toggleConversationAI(
  conversationId: string,
  aiEnabled: boolean
): Promise<AIConversationStatusResponse> {
  const resp = await apiClient.patch<AIConversationStatusResponse>(
    `/ai/conversations/${conversationId}/toggle`,
    { ai_enabled: aiEnabled }
  );
  return resp.data;
}

export async function getConversationAIStatus(
  conversationId: string
): Promise<AIConversationStatusResponse> {
  const resp = await apiClient.get<AIConversationStatusResponse>(
    `/ai/conversations/${conversationId}/status`
  );
  return resp.data;
}

export async function processConversationRAG(
  conversationId: string,
  params?: { top_k?: number; prompt_override?: string; max_history_messages?: number }
): Promise<RAGProcessResponse> {
  const resp = await apiClient.post<RAGProcessResponse>(
    `/ai/conversations/${conversationId}/rag`,
    params || { top_k: 5 }
  );
  return resp.data;
}
