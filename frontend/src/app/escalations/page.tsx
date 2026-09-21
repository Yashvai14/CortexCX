'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Button, Card, ErrorBanner, SkeletonCard, Badge } from '@/components/ui';
import { listEscalations, type EscalationItem } from '@/api/escalations';
import { AxiosError } from 'axios';

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const data = await listEscalations();
      setEscalations(data);
    } catch (err) {
      if (err instanceof AxiosError) {
        setError(err.response?.data?.detail ?? err.message);
      } else {
        setError('Failed to load escalations');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <ProtectedRoute>
      <AppLayout title="Human Handoff & Escalations">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Human Escalation Queue</h2>
            <p className="text-sm text-slate-500 mt-1">
              Conversations requiring human agent intervention due to low AI confidence or explicit customer request.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={load}>
            Refresh Queue
          </Button>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SkeletonCard /><SkeletonCard />
          </div>
        ) : escalations.length === 0 ? (
          <Card className="p-10 text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 mb-3">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-slate-800">All clear! No pending escalations</h3>
            <p className="text-sm text-slate-500 mt-1">The AI engine is successfully handling inquiries within high confidence thresholds.</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {escalations.map((esc) => (
              <Card key={esc.id} className="p-5 hover:border-indigo-200 transition-colors">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">{esc.customer_name}</span>
                      {esc.customer_email && (
                        <span className="text-xs text-slate-400">({esc.customer_email})</span>
                      )}
                      <Badge variant={esc.status === 'in_progress' ? 'warning' : 'danger'}>
                        {esc.status.replace('_', ' ').toUpperCase()}
                      </Badge>
                      {esc.confidence_score !== undefined && (
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                          Score: {esc.confidence_score.toFixed(2)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-600 mt-1 font-medium">{esc.reason}</p>
                    {esc.summary && (
                      <p className="text-xs text-slate-400 mt-1 line-clamp-1">{esc.summary}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Link href={`/escalations/${esc.id}`}>
                      <Button size="sm">
                        Open Agent Assist
                      </Button>
                    </Link>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}
