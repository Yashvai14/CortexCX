// =====================================================================
// All TypeScript types matching backend Pydantic schemas exactly
// =====================================================================

export type UserRole = 'OWNER' | 'ADMIN' | 'AGENT';

export interface Workspace {
  id: string;
  name: string;
  slug: string;
}

export interface User {
  id: string;
  workspace_id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RegisterResponse {
  message: string;
  workspace: Workspace;
  user: User;
  token: TokenResponse;
}

// =====================================================================
// Customer
// =====================================================================

export type CustomerStatus = 'active' | 'inactive' | 'blocked';

export interface Customer {
  id: string;
  workspace_id: string;
  full_name: string;
  email: string;
  phone: string | null;
  company_name: string | null;
  status: CustomerStatus;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreateRequest {
  full_name: string;
  email: string;
  phone?: string;
  company_name?: string;
  status?: CustomerStatus;
}

export interface CustomerUpdateRequest {
  full_name?: string;
  email?: string;
  phone?: string;
  company_name?: string;
  status?: CustomerStatus;
}

// =====================================================================
// Conversation & Message
// =====================================================================

export type ConversationStatus = 'open' | 'pending' | 'resolved' | 'closed';
export type AIState = 'idle' | 'processing' | 'responded' | 'failed' | 'disabled';
export type MessageSenderType = 'customer' | 'agent' | 'ai' | 'system';

export interface Conversation {
  id: string;
  customer_id: string;
  subject: string;
  status: ConversationStatus;
  ai_enabled: boolean;
  ai_state: AIState;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_type: MessageSenderType;
  sender_user_id: string | null;
  content: string;
  created_at: string;
}

export interface ConversationCreateRequest {
  customer_id: string;
  subject: string;
}

export interface ConversationUpdateRequest {
  subject?: string;
  status?: ConversationStatus;
}

export interface MessageCreateRequest {
  content: string;
  sender_type?: MessageSenderType;
}

// =====================================================================
// AI
// =====================================================================

export interface AIProcessConversationResponse {
  conversation_id: string;
  message: Message;
  ai_state: string;
  provider: string;
}

export interface AIConversationStatusResponse {
  conversation_id: string;
  ai_enabled: boolean;
  ai_state: string;
  total_ai_messages: number;
  last_processed_at: string | null;
}

export interface RAGSourceCitation {
  chunk_id: string;
  document_id: string;
  knowledge_source_id: string | null;
  document_title: string | null;
  relevance_score: number;
  content: string;
  metadata_json: Record<string, unknown> | null;
}

export interface RAGProcessResponse {
  conversation_id: string;
  message: Message;
  ai_state: string;
  provider: string;
  sources: RAGSourceCitation[];
}

// =====================================================================
// Knowledge Base
// =====================================================================

export type KnowledgeSourceType = 'txt' | 'markdown' | 'pdf' | 'docx' | 'url';
export type KnowledgeSourceStatus = 'active' | 'inactive';
export type DocumentStatus = 'pending' | 'chunked' | 'embedded' | 'failed';

export interface KnowledgeSource {
  id: string;
  workspace_id: string;
  name: string;
  source_type: KnowledgeSourceType;
  source_url: string | null;
  status: KnowledgeSourceStatus;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocument {
  id: string;
  workspace_id: string;
  knowledge_source_id: string;
  title: string;
  filename: string | null;
  content: string;
  metadata_json: Record<string, unknown> | null;
  status: DocumentStatus;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  workspace_id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  has_embedding: boolean;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeSearchResult {
  chunk_id: string;
  document_id: string;
  knowledge_source_id: string | null;
  content: string;
  chunk_index: number;
  similarity_score: number;
  metadata_json: Record<string, unknown> | null;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeSearchResult[];
  total: number;
}

// =====================================================================
// Workspace / Members
// =====================================================================

export interface WorkspaceUser {
  id: string;
  workspace_id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface Member {
  id: string;
  workspace_id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface MessageResponse {
  message: string;
}

// =====================================================================
// API Error
// =====================================================================

export interface APIError {
  detail: string | { msg: string; type: string }[];
}
