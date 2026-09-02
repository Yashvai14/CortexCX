import apiClient from './client';
import type {
  Conversation,
  ConversationCreateRequest,
  ConversationUpdateRequest,
  ConversationStatus,
  Message,
  MessageCreateRequest,
} from '@/types';

export async function listConversations(params?: {
  customer_id?: string;
  status?: ConversationStatus;
}): Promise<Conversation[]> {
  const resp = await apiClient.get<Conversation[]>('/conversations', { params });
  return resp.data;
}

export async function getConversation(id: string): Promise<Conversation> {
  const resp = await apiClient.get<Conversation>(`/conversations/${id}`);
  return resp.data;
}

export async function createConversation(
  data: ConversationCreateRequest
): Promise<Conversation> {
  const resp = await apiClient.post<Conversation>('/conversations', data);
  return resp.data;
}

export async function updateConversation(
  id: string,
  data: ConversationUpdateRequest
): Promise<Conversation> {
  const resp = await apiClient.patch<Conversation>(`/conversations/${id}`, data);
  return resp.data;
}

export async function listMessages(conversationId: string): Promise<Message[]> {
  const resp = await apiClient.get<Message[]>(
    `/conversations/${conversationId}/messages`
  );
  return resp.data;
}

export async function createMessage(
  conversationId: string,
  data: MessageCreateRequest
): Promise<Message> {
  const resp = await apiClient.post<Message>(
    `/conversations/${conversationId}/messages`,
    data
  );
  return resp.data;
}
