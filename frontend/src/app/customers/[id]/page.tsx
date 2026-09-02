'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Card, Spinner, ErrorBanner, ConversationStatusBadge, AIStateBadge, Badge, Button } from '@/components/ui';
import { getCustomer } from '@/api/customers';
import { listConversations } from '@/api/conversations';
import type { Customer, Conversation } from '@/types';
import { AxiosError } from 'axios';

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const [cust, convs] = await Promise.all([
          getCustomer(id),
          listConversations({ customer_id: id }),
        ]);
        setCustomer(cust);
        setConversations(convs);
      } catch (err) {
        if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) {
    return (
      <ProtectedRoute>
        <AppLayout>
          <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>
        </AppLayout>
      </ProtectedRoute>
    );
  }

  if (error || !customer) {
    return (
      <ProtectedRoute>
        <AppLayout>
          <ErrorBanner message={error || 'Customer not found'} />
        </AppLayout>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <AppLayout>
        {/* Back */}
        <Link href="/customers" className="text-xs text-slate-400 hover:text-slate-700 flex items-center gap-1 mb-4">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Customers
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Profile card */}
          <div className="space-y-4">
            <Card className="p-6">
              <div className="flex items-center gap-4 mb-5">
                <div className="h-12 w-12 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-lg">
                  {customer.full_name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <p className="font-semibold text-slate-900">{customer.full_name}</p>
                  <Badge color={customer.status === 'active' ? 'green' : customer.status === 'blocked' ? 'red' : 'slate'}>
                    {customer.status}
                  </Badge>
                </div>
              </div>
              <dl className="space-y-2.5 text-sm">
                <div className="flex justify-between gap-2">
                  <dt className="text-slate-500">Email</dt>
                  <dd className="text-slate-800 text-right truncate max-w-[180px]">{customer.email}</dd>
                </div>
                {customer.phone && (
                  <div className="flex justify-between gap-2">
                    <dt className="text-slate-500">Phone</dt>
                    <dd className="text-slate-800">{customer.phone}</dd>
                  </div>
                )}
                {customer.company_name && (
                  <div className="flex justify-between gap-2">
                    <dt className="text-slate-500">Company</dt>
                    <dd className="text-slate-800">{customer.company_name}</dd>
                  </div>
                )}
                <div className="flex justify-between gap-2">
                  <dt className="text-slate-500">Created</dt>
                  <dd className="text-slate-800">{new Date(customer.created_at).toLocaleDateString()}</dd>
                </div>
              </dl>
            </Card>
          </div>

          {/* Conversations */}
          <div className="lg:col-span-2">
            <Card>
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-700">
                  Conversations ({conversations.length})
                </h3>
              </div>
              <div className="divide-y divide-slate-50">
                {conversations.length === 0 ? (
                  <p className="px-5 py-8 text-sm text-slate-400 text-center">
                    No conversations with this customer yet.
                  </p>
                ) : (
                  conversations.map((conv) => (
                    <div key={conv.id} className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 transition-colors">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">{conv.subject}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <ConversationStatusBadge status={conv.status} />
                          <AIStateBadge state={conv.ai_state} />
                          <span className="text-xs text-slate-400">{new Date(conv.updated_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <Link href={`/conversations/${conv.id}`} className="ml-4 flex-shrink-0">
                        <Button variant="ghost" size="sm">Open</Button>
                      </Link>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}
