'use client';

import { useEffect, useState, FormEvent } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Button, Card, Spinner, ErrorBanner, Badge } from '@/components/ui';
import {
  getEscalation,
  claimEscalation,
  respondToEscalation,
  returnToAi,
  submitAgentFeedback,
  type EscalationDetail,
} from '@/api/escalations';
import { AxiosError } from 'axios';
import { LinkedTickets } from '@/components/tickets/LinkedTickets';

export default function EscalationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [detail, setDetail] = useState<EscalationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);
  const [actionSuccess, setActionSuccess] = useState('');

  const load = async () => {
    try {
      const data = await getEscalation(id);
      setDetail(data);
      if (data.suggested_reply && !replyText) {
        setReplyText(data.suggested_reply);
      }
    } catch (err) {
      if (err instanceof AxiosError) {
        setError(err.response?.data?.detail ?? err.message);
      } else {
        setError('Failed to load escalation detail');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const handleClaim = async () => {
    try {
      await claimEscalation(id);
      setActionSuccess('Escalation claimed.');
      load();
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    }
  };

  const handleSendReply = async (resolve: boolean = false) => {
    if (!replyText.trim()) return;
    setSending(true);
    setError('');
    try {
      await respondToEscalation(id, replyText.trim(), resolve);
      // If agent modified suggested reply, submit feedback for learning engine
      if (detail?.suggested_reply && replyText.trim() !== detail.suggested_reply.trim()) {
        await submitAgentFeedback({
          conversation_id: detail.conversation_id,
          original_response: detail.suggested_reply,
          corrected_response: replyText.trim(),
          reason: 'Agent refined AI suggestion',
        });
      }
      setActionSuccess(resolve ? 'Replied and resolved escalation.' : 'Reply sent to customer.');
      load();
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSending(false);
    }
  };

  const handleReturnToAi = async () => {
    try {
      await returnToAi(id);
      setActionSuccess('Conversation returned to AI engine.');
      router.push('/escalations');
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    }
  };

  if (loading) {
    return (
      <ProtectedRoute>
        <AppLayout title="Agent Assist">
          <div className="py-20 flex justify-center"><Spinner /></div>
        </AppLayout>
      </ProtectedRoute>
    );
  }

  if (!detail) {
    return (
      <ProtectedRoute>
        <AppLayout title="Agent Assist">
          <ErrorBanner message="Escalation not found" />
        </AppLayout>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <AppLayout title="Agent Assist & Human Takeover">
        <div className="mb-4 flex items-center justify-between">
          <Link href="/escalations" className="text-xs text-indigo-600 hover:underline flex items-center gap-1">
            ← Back to Queue
          </Link>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={handleClaim}>
              Claim Ticket
            </Button>
            <Button variant="danger" size="sm" onClick={handleReturnToAi}>
              Return to AI
            </Button>
          </div>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
        {actionSuccess && (
          <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-md">
            {actionSuccess}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main conversation column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Conversation Thread */}
            <Card className="p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-4">Conversation Thread</h3>
              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                {detail.messages.map((m) => {
                  const isAgent = m.sender_type === 'agent';
                  const isAI = m.sender_type === 'ai';
                  return (
                    <div
                      key={m.id}
                      className={`p-3.5 rounded-lg max-w-[85%] text-sm ${
                        isAgent
                          ? 'ml-auto bg-indigo-600 text-white'
                          : isAI
                          ? 'mr-auto bg-amber-50 text-amber-900 border border-amber-200'
                          : 'mr-auto bg-slate-100 text-slate-800'
                      }`}
                    >
                      <p className="text-xs font-semibold mb-1 opacity-75">
                        {isAgent ? 'Support Agent (You)' : isAI ? '🤖 AI Response' : 'Customer'}
                      </p>
                      <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Agent Reply Composer */}
            <Card className="p-5 border-indigo-200 bg-indigo-50/20">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">Agent Reply Composer</h3>
              <textarea
                rows={4}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Type your response to the customer..."
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-surface"
              />
              <div className="mt-3 flex items-center justify-between">
                <p className="text-xs text-slate-400">
                  Submitting will send directly to customer and store verified response in the learning dataset.
                </p>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="secondary" onClick={() => handleSendReply(false)} disabled={sending}>
                    {sending ? 'Sending...' : 'Send Message'}
                  </Button>
                  <Button size="sm" onClick={() => handleSendReply(true)} disabled={sending}>
                    Send & Resolve
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          {/* Right Sidebar: Agent Assist Intelligence */}
          <div className="space-y-6">
            <LinkedTickets
              conversationId={detail.conversation_id}
              customerId={detail.customer.id}
              defaultSubject={`Escalation: ${detail.conversation_subject}`}
              defaultDescription={[detail.reason && `Reason: ${detail.reason}`, detail.summary && `Summary: ${detail.summary}`].filter(Boolean).join('\n\n')}
              defaultPriority="high"
              defaultCategory="Escalation"
            />
            {/* Reason & Status */}
            <Card className="p-5">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">Handoff Diagnostics</h3>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-slate-500">Status:</span>
                  <Badge className="ml-2" variant="warning">{detail.status.toUpperCase()}</Badge>
                </div>
                <div>
                  <span className="text-xs text-slate-500">Confidence Score:</span>
                  <span className="ml-2 text-xs font-mono font-bold text-slate-800">
                    {detail.confidence_score !== undefined ? `${(detail.confidence_score * 100).toFixed(0)}%` : 'N/A'}
                  </span>
                </div>
                <div className="pt-2 border-t border-slate-100">
                  <span className="text-xs text-slate-500 block">Trigger Reason:</span>
                  <p className="text-xs font-medium text-rose-700 mt-0.5">{detail.reason}</p>
                </div>
              </div>
            </Card>

            {/* AI Suggested Response */}
            {detail.suggested_reply && (
              <Card className="p-5 border-amber-200 bg-amber-50/40">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold text-amber-900 uppercase tracking-wide">AI Suggested Reply</h3>
                  <button
                    onClick={() => setReplyText(detail.suggested_reply || '')}
                    className="text-xs text-indigo-600 hover:underline font-medium"
                  >
                    Insert Text
                  </button>
                </div>
                <p className="text-xs text-slate-700 italic bg-surface p-3 rounded border border-amber-200/60 leading-relaxed">
                  "{detail.suggested_reply}"
                </p>
              </Card>
            )}

            {/* Customer Profile & Memories */}
            <Card className="p-5">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-3">Customer Profile & Memory</h3>
              <div className="text-xs space-y-1.5 mb-4">
                <p><strong className="text-slate-700">Name:</strong> {detail.customer.name}</p>
                <p><strong className="text-slate-700">Email:</strong> {detail.customer.email}</p>
                {detail.customer.company && <p><strong className="text-slate-700">Company:</strong> {detail.customer.company}</p>}
              </div>

              <h4 className="text-xs font-semibold text-slate-600 mb-1.5 border-t border-slate-100 pt-3">Episodic Memories</h4>
              {detail.customer_memories.length === 0 ? (
                <p className="text-xs text-slate-400">No episodic memories recorded yet.</p>
              ) : (
                <ul className="text-xs text-slate-600 space-y-1 list-disc pl-4">
                  {detail.customer_memories.map((m, idx) => (
                    <li key={idx}>{m}</li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}
