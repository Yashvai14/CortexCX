import apiClient from './client';

export type TicketStatus = 'open' | 'in_progress' | 'waiting' | 'resolved' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface UserBrief {
  id: string;
  full_name: string;
}

export interface TicketComment {
  id: string;
  ticket_id: string;
  author: UserBrief | null;
  content: string;
  is_internal: boolean;
  is_event: boolean;
  created_at: string;
}

export interface Ticket {
  id: string;
  number: number;
  reference: string;
  subject: string;
  description: string | null;
  category: string | null;
  status: TicketStatus;
  priority: TicketPriority;
  customer: { id: string; full_name: string; email: string } | null;
  conversation_id: string | null;
  assignee: UserBrief | null;
  created_by: UserBrief | null;
  due_at: string | null;
  sla_breached: boolean;
  first_response_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  comments?: TicketComment[];
}

export interface TicketStats {
  total: number;
  by_status: Record<TicketStatus, number>;
  overdue: number;
  unassigned: number;
  assigned_to_me: number;
}

export interface TicketFilters {
  status?: TicketStatus;
  priority?: TicketPriority;
  mine?: boolean;
  unassigned?: boolean;
  conversation_id?: string;
  q?: string;
}

export interface TicketCreateRequest {
  subject: string;
  description?: string;
  category?: string;
  priority?: TicketPriority;
  customer_id?: string;
  assignee_id?: string;
  conversation_id?: string;
}

export interface TicketUpdateRequest {
  subject?: string;
  description?: string;
  category?: string;
  status?: TicketStatus;
  priority?: TicketPriority;
  assignee_id?: string;
  unassign?: boolean;
}

export async function listTickets(filters: TicketFilters = {}): Promise<Ticket[]> {
  const params: Record<string, string | boolean> = {};
  if (filters.status) params.status = filters.status;
  if (filters.priority) params.priority = filters.priority;
  if (filters.mine) params.mine = true;
  if (filters.unassigned) params.unassigned = true;
  if (filters.conversation_id) params.conversation_id = filters.conversation_id;
  if (filters.q) params.q = filters.q;
  const resp = await apiClient.get<Ticket[]>('/tickets', { params });
  return resp.data;
}

export async function getTicketStats(): Promise<TicketStats> {
  const resp = await apiClient.get<TicketStats>('/tickets/stats');
  return resp.data;
}

export async function getTicket(id: string): Promise<Ticket> {
  const resp = await apiClient.get<Ticket>(`/tickets/${id}`);
  return resp.data;
}

export async function createTicket(data: TicketCreateRequest): Promise<Ticket> {
  const resp = await apiClient.post<Ticket>('/tickets', data);
  return resp.data;
}

export async function updateTicket(id: string, data: TicketUpdateRequest): Promise<Ticket> {
  const resp = await apiClient.patch<Ticket>(`/tickets/${id}`, data);
  return resp.data;
}

export async function addTicketComment(
  id: string,
  content: string,
  is_internal: boolean,
): Promise<TicketComment> {
  const resp = await apiClient.post<TicketComment>(`/tickets/${id}/comments`, { content, is_internal });
  return resp.data;
}

export async function deleteTicket(id: string): Promise<void> {
  await apiClient.delete(`/tickets/${id}`);
}
