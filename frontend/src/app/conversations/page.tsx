'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import {
  Button, Card, SkeletonRow, EmptyState, ErrorBanner,
  ConversationStatusBadge, AIStateBadge, Badge,
} from '@/components/ui';
import { listConversations } from '@/api/conversations';
import { listCustomers } from '@/api/customers';
import type { Conversation, Customer, ConversationStatus } from '@/types';
import { AxiosError } from 'axios';

const STATUS_FILTERS: Array<{ label: string; value: ConversationStatus | 'all' }> = [
  { label: 'All', value: 'all' },
  { label: 'Open', value: 'open' },
  { label: 'Pending', value: 'pending' },
  { label: 'Resolved', value: 'resolved' },
  { label: 'Closed', value: 'closed' },
];

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [customers, setCustomers] = useState<Map<string, Customer>>(new Map());
  const [filter, setFilter] = useState<ConversationStatus | 'all'>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const params = filter !== 'all' ? { status: filter } : undefined;
        const [convs, custs] = await Promise.all([
          listConversations(params),
          listCustomers(),
        ]);
        setConversations(convs);
        const custMap = new Map(custs.map((c) => [c.id, c]));
        setCustomers(custMap);
      } catch (err) {
        if (err instanceof AxiosError) {
          setError(err.response?.data?.detail ?? err.message);
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [filter]);

  return (
    <ProtectedRoute>
      <AppLayout title="Conversations">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Conversations</h2>
            <p className="text-sm text-slate-500">{conversations.length} total</p>
          </div>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {/* Filter tabs */}
        <div className="flex items-center gap-1 mb-4 bg-surface border border-slate-200 rounded-lg p-1 w-fit">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                filter === f.value
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Table */}
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Subject</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Customer</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">AI</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Updated</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => <tr key={i}><td colSpan={6}><SkeletonRow cols={5} /></td></tr>)
                ) : conversations.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <EmptyState
                        title="No conversations"
                        description="Conversations will appear here when customers reach out."
                        icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>}
                      />
                    </td>
                  </tr>
                ) : (
                  conversations.map((conv) => {
                    const cust = customers.get(conv.customer_id);
                    return (
                      <tr key={conv.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3.5 font-medium text-slate-800 max-w-xs truncate">{conv.subject}</td>
                        <td className="px-5 py-3.5 text-slate-600">{cust?.full_name ?? '—'}</td>
                        <td className="px-5 py-3.5"><ConversationStatusBadge status={conv.status} /></td>
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-1.5">
                            <AIStateBadge state={conv.ai_state} />
                            {!conv.ai_enabled && <Badge color="slate">disabled</Badge>}
                          </div>
                        </td>
                        <td className="px-5 py-3.5 text-slate-400 text-xs">{fmtDate(conv.updated_at)}</td>
                        <td className="px-5 py-3.5">
                          <Link href={`/conversations/${conv.id}`}>
                            <Button variant="ghost" size="sm">Open</Button>
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </AppLayout>
    </ProtectedRoute>
  );
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
