import apiClient from './client';

export interface EscalationItem {
  id: string;
  conversation_id: string;
  customer_id: string;
  customer_name: string;
  customer_email?: string;
  status: 'pending' | 'in_progress' | 'resolved' | 'returned_to_ai';
  reason: string;
  confidence_score?: number;
  summary?: string;
  suggested_reply?: string;
  assigned_agent_name?: string;
  created_at: string;
}

export interface EscalationDetail {
  id: string;
  conversation_id: string;
  conversation_subject: string;
  customer: {
    id?: string;
    name: string;
    email: string;
    phone?: string;
    company?: string;
  };
  status: string;
  reason: string;
  confidence_score?: number;
  summary?: string;
  suggested_reply?: string;
  customer_memories: string[];
  messages: Array<{
    id: string;
    sender_type: string;
    content: string;
    created_at?: string;
  }>;
}

export async function listEscalations(): Promise<EscalationItem[]> {
  const resp = await apiClient.get<EscalationItem[]>('/escalations');
  return resp.data;
}

export async function getEscalation(id: string): Promise<EscalationDetail> {
  const resp = await apiClient.get<EscalationDetail>(`/escalations/${id}`);
  return resp.data;
}

export async function claimEscalation(id: string): Promise<void> {
  await apiClient.post(`/escalations/${id}/claim`);
}

export async function respondToEscalation(
  id: string,
  content: string,
  resolve: boolean = false
): Promise<void> {
  await apiClient.post(`/escalations/${id}/respond`, { content, resolve });
}

export async function returnToAi(id: string): Promise<void> {
  await apiClient.post(`/escalations/${id}/return-to-ai`);
}

export async function submitAgentFeedback(data: {
  conversation_id: string;
  message_id?: string;
  original_response: string;
  corrected_response: string;
  reason?: string;
}): Promise<void> {
  await apiClient.post('/escalations/feedback', data);
}
