'use client';

import { useEffect, useState, useRef, FormEvent } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import {
  Button, Card, Spinner, ErrorBanner, EmptyState,
  ConversationStatusBadge, AIStateBadge, Badge,
} from '@/components/ui';
import {
  getConversation, listMessages, createMessage, updateConversation,
} from '@/api/conversations';
import {
  processConversationAI, processConversationRAG,
  toggleConversationAI, getConversationAIStatus,
} from '@/api/ai';
import { getCustomer } from '@/api/customers';
import type { Conversation, Message, Customer, RAGSourceCitation } from '@/types';
import { AxiosError } from 'axios';
import { useAuth } from '@/context/AuthContext';

type SenderType = 'customer' | 'agent' | 'ai' | 'system';

const senderStyle: Record<SenderType, string> = {
  customer: 'bg-slate-100 text-slate-800 self-start',
  agent: 'bg-indigo-600 text-white self-end',
  ai: 'bg-emerald-50 text-emerald-900 border border-emerald-200 self-start',
  system: 'bg-amber-50 text-amber-800 border border-amber-200 self-start text-xs italic',
};

const senderLabel: Record<SenderType, string> = {
  customer: 'Customer',
  agent: 'Agent',
  ai: '✦ AI',
  system: 'System',
};

export default function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { role } = useAuth();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  const [aiProcessing, setAiProcessing] = useState(false);
  const [ragProcessing, setRagProcessing] = useState(false);
  const [ragSources, setRagSources] = useState<RAGSourceCitation[]>([]);
  const [showSources, setShowSources] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = async () => {
    try {
      const [conv, msgs] = await Promise.all([
        getConversation(id),
        listMessages(id),
      ]);
      setConversation(conv);
      setMessages(msgs);
      if (conv.customer_id) {
        const cust = await getCustomer(conv.customer_id);
        setCustomer(cust);
      }
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!messageText.trim()) return;
    setSending(true);
    try {
      const msg = await createMessage(id, { content: messageText, sender_type: 'agent' });
      setMessages((prev) => [...prev, msg]);
      setMessageText('');
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSending(false);
    }
  };

  const handleProcessAI = async () => {
    setAiProcessing(true);
    setError('');
    try {
      const result = await processConversationAI(id);
      setMessages((prev) => [...prev, result.message]);
      const updated = await getConversation(id);
      setConversation(updated);
    } catch (err) {
      if (err instanceof AxiosError) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : (err.message ?? 'AI processing failed'));
      }
    } finally {
      setAiProcessing(false);
    }
  };

  const handleRAG = async () => {
    setRagProcessing(true);
    setError('');
    try {
      const result = await processConversationRAG(id, { top_k: 5 });
      setMessages((prev) => [...prev, result.message]);
      setRagSources(result.sources);
      setShowSources(true);
      const updated = await getConversation(id);
      setConversation(updated);
    } catch (err) {
      if (err instanceof AxiosError) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : (err.message ?? 'RAG processing failed'));
      }
    } finally {
      setRagProcessing(false);
    }
  };

  const handleToggleAI = async () => {
    if (!conversation) return;
    try {
      await toggleConversationAI(id, !conversation.ai_enabled);
      const updated = await getConversation(id);
      setConversation(updated);
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    }
  };

  const handleClose = async () => {
    if (!conversation) return;
    try {
      const updated = await updateConversation(id, { status: 'closed' });
      setConversation(updated);
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    }
  };

  if (loading) {
    return (
      <ProtectedRoute>
        <AppLayout>
          <div className="flex items-center justify-center h-64">
            <Spinner size="lg" />
          </div>
        </AppLayout>
      </ProtectedRoute>
    );
  }

  if (!conversation) {
    return (
      <ProtectedRoute>
        <AppLayout>
          <ErrorBanner message="Conversation not found." />
        </AppLayout>
      </ProtectedRoute>
    );
  }

  const canEdit = role === 'OWNER' || role === 'ADMIN' || role === 'AGENT';

  return (
    <ProtectedRoute>
      <AppLayout>
        {/* Back + header */}
        <div className="mb-4">
          <Link href="/conversations" className="text-xs text-slate-400 hover:text-slate-700 flex items-center gap-1 mb-3">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Conversations
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{conversation.subject}</h2>
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                <ConversationStatusBadge status={conversation.status} />
                <AIStateBadge state={conversation.ai_state} />
                {!conversation.ai_enabled && <Badge color="slate">AI disabled</Badge>}
                {customer && (
                  <Link href={`/customers/${customer.id}`} className="text-xs text-indigo-600 hover:underline">
                    {customer.full_name}
                  </Link>
                )}
              </div>
            </div>

            {canEdit && (
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleToggleAI}
                  disabled={aiProcessing || ragProcessing}
                >
                  {conversation.ai_enabled ? 'Disable AI' : 'Enable AI'}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleProcessAI}
                  loading={aiProcessing}
                  disabled={!conversation.ai_enabled || ragProcessing}
                >
                  Process AI
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleRAG}
                  loading={ragProcessing}
                  disabled={!conversation.ai_enabled || aiProcessing}
                >
                  ✦ RAG Response
                </Button>
                {conversation.status !== 'closed' && (
                  <Button variant="ghost" size="sm" onClick={handleClose}>
                    Close
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Message thread */}
          <div className="lg:col-span-2 flex flex-col gap-4">
            <Card className="flex flex-col" style={{ minHeight: '480px' }}>
              <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3" style={{ maxHeight: '520px' }}>
                {messages.length === 0 ? (
                  <EmptyState
                    title="No messages yet"
                    description="Send the first message or trigger AI processing."
                  />
                ) : (
                  messages.map((msg) => {
                    const s = msg.sender_type as SenderType;
                    return (
                      <div key={msg.id} className={`flex flex-col max-w-[80%] ${s === 'agent' ? 'self-end items-end' : 'self-start items-start'}`}>
                        <span className="text-xs text-slate-400 mb-1 px-1">
                          {senderLabel[s] ?? s} · {fmtTime(msg.created_at)}
                        </span>
                        <div className={`rounded-xl px-4 py-2.5 text-sm leading-relaxed ${senderStyle[s] ?? 'bg-slate-100 text-slate-800'}`}>
                          {msg.content}
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={bottomRef} />
              </div>

              {/* Composer */}
              {canEdit && conversation.status !== 'closed' && (
                <div className="border-t border-slate-100 p-4">
                  <form onSubmit={handleSendMessage} className="flex gap-2">
                    <input
                      type="text"
                      value={messageText}
                      onChange={(e) => setMessageText(e.target.value)}
                      placeholder="Type a message…"
                      className="flex-1 border border-slate-200 rounded-lg px-3.5 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    />
                    <Button type="submit" loading={sending} disabled={!messageText.trim()}>
                      Send
                    </Button>
                  </form>
                </div>
              )}
            </Card>
          </div>

          {/* Side panel */}
          <div className="space-y-4">
            {/* Customer info */}
            {customer && (
              <Card className="p-5">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Customer</h3>
                <p className="text-sm font-semibold text-slate-800">{customer.full_name}</p>
                <p className="text-xs text-slate-500 mt-0.5">{customer.email}</p>
                {customer.phone && <p className="text-xs text-slate-500">{customer.phone}</p>}
                {customer.company_name && <p className="text-xs text-slate-500">{customer.company_name}</p>}
                <Link href={`/customers/${customer.id}`} className="mt-3 inline-block text-xs text-indigo-600 hover:underline">
                  View profile →
                </Link>
              </Card>
            )}

            {/* AI Status */}
            <Card className="p-5">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">AI Status</h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">State</span>
                  <AIStateBadge state={conversation.ai_state} />
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">AI Enabled</span>
                  <span className={conversation.ai_enabled ? 'text-emerald-600 font-medium' : 'text-slate-400'}>
                    {conversation.ai_enabled ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Messages</span>
                  <span className="text-slate-700 font-medium">{messages.length}</span>
                </div>
              </div>
            </Card>

            {/* RAG Sources */}
            {showSources && ragSources.length > 0 && (
              <Card className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Knowledge Sources</h3>
                  <button onClick={() => setShowSources(false)} className="text-xs text-slate-400 hover:text-slate-600">✕</button>
                </div>
                <div className="space-y-3">
                  {ragSources.map((src) => (
                    <div key={src.chunk_id} className="border border-slate-100 rounded-lg p-3 bg-emerald-50/30">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-slate-700 truncate">{src.document_title ?? 'Document'}</span>
                        <span className="text-xs text-emerald-600 font-medium ml-2 flex-shrink-0">
                          {(src.relevance_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-3">{src.content}</p>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}
