'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Card, SkeletonCard, ConversationStatusBadge, AIStateBadge, ErrorBanner } from '@/components/ui';
import { useAuth } from '@/context/AuthContext';
import { listCustomers } from '@/api/customers';
import { listConversations } from '@/api/conversations';
import type { Customer, Conversation } from '@/types';
import { AxiosError } from 'axios';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-3xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [c, cv] = await Promise.all([listCustomers(), listConversations()]);
        setCustomers(c);
        setConversations(cv);
      } catch (err) {
        if (err instanceof AxiosError) {
          setError(err.response?.data?.detail ?? err.message);
        } else {
          setError('Failed to load dashboard data');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const openConversations = conversations.filter((c) => c.status === 'open');
  const aiConversations = conversations.filter((c) => c.ai_enabled);
  const recentConversations = [...conversations]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);
  const recentCustomers = [...customers]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return (
    <ProtectedRoute>
      <AppLayout title="Dashboard">
        {/* Greeting */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-slate-900">
            Good {getTimeOfDay()}, {user?.full_name?.split(' ')[0]}
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Here's what's happening across your workspace.
          </p>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {loading ? (
            <>
              <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
            </>
          ) : (
            <>
              <StatCard label="Total Customers" value={customers.length} sub="across workspace" />
              <StatCard label="Total Conversations" value={conversations.length} sub="all time" />
              <StatCard label="Open Conversations" value={openConversations.length} sub="currently active" />
              <StatCard label="AI-Enabled Conversations" value={aiConversations.length} sub="with AI enabled" />
            </>
          )}
        </div>

        {/* Recent rows */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Conversations */}
          <Card>
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-700">Recent Conversations</h3>
              <Link href="/conversations" className="text-xs text-indigo-600 hover:underline">
                View all
              </Link>
            </div>
            <div className="divide-y divide-slate-50">
              {loading ? (
                [1, 2, 3].map((i) => (
                  <div key={i} className="px-5 py-3 animate-pulse flex gap-3">
                    <div className="h-4 bg-slate-200 rounded flex-1" />
                    <div className="h-4 bg-slate-100 rounded w-16" />
                  </div>
                ))
              ) : recentConversations.length === 0 ? (
                <p className="px-5 py-6 text-sm text-slate-400 text-center">
                  No conversations yet
                </p>
              ) : (
                recentConversations.map((conv) => (
                  <Link
                    key={conv.id}
                    href={`/conversations/${conv.id}`}
                    className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800 truncate">{conv.subject}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{formatDate(conv.updated_at)}</p>
                    </div>
                    <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                      <AIStateBadge state={conv.ai_state} />
                      <ConversationStatusBadge status={conv.status} />
                    </div>
                  </Link>
                ))
              )}
            </div>
          </Card>

          {/* Recent Customers */}
          <Card>
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-700">Recent Customers</h3>
              <Link href="/customers" className="text-xs text-indigo-600 hover:underline">
                View all
              </Link>
            </div>
            <div className="divide-y divide-slate-50">
              {loading ? (
                [1, 2, 3].map((i) => (
                  <div key={i} className="px-5 py-3 animate-pulse flex gap-3">
                    <div className="h-4 bg-slate-200 rounded flex-1" />
                    <div className="h-4 bg-slate-100 rounded w-24" />
                  </div>
                ))
              ) : recentCustomers.length === 0 ? (
                <p className="px-5 py-6 text-sm text-slate-400 text-center">
                  No customers yet
                </p>
              ) : (
                recentCustomers.map((cust) => (
                  <Link
                    key={cust.id}
                    href={`/customers/${cust.id}`}
                    className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800 truncate">{cust.full_name}</p>
                      <p className="text-xs text-slate-400 mt-0.5 truncate">{cust.email}</p>
                    </div>
                    <p className="text-xs text-slate-400 ml-3 flex-shrink-0">{formatDate(cust.created_at)}</p>
                  </Link>
                ))
              )}
            </div>
          </Card>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

function getTimeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return 'morning';
  if (h < 17) return 'afternoon';
  return 'evening';
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}
