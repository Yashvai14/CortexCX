'use client';

import { useEffect, useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Card, SkeletonCard, ErrorBanner } from '@/components/ui';
import { getAnalyticsOverview, type AnalyticsOverview } from '@/api/analytics';
import { AxiosError } from 'axios';

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const res = await getAnalyticsOverview();
      setData(res);
    } catch (err) {
      if (err instanceof AxiosError) {
        setError(err.response?.data?.detail ?? err.message);
      } else {
        setError('Failed to load analytics');
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
      <AppLayout title="Executive Analytics & CX Intelligence">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-slate-900">Performance & AI Resolution Metrics</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time analytics aggregated across all customer channels, tools, and AI interactions.
          </p>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {loading || !data ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
          </div>
        ) : (
          <>
            {/* Top KPI Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <Card className="p-5 border-l-4 border-indigo-500">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">AI Resolution Rate</p>
                <p className="mt-1 text-3xl font-extrabold text-indigo-600">{data.ai_resolution_rate}%</p>
                <p className="mt-1 text-xs text-slate-400">resolved without human handoff</p>
              </Card>

              <Card className="p-5 border-l-4 border-emerald-500">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Total Conversations</p>
                <p className="mt-1 text-3xl font-extrabold text-slate-900">{data.total_conversations}</p>
                <p className="mt-1 text-xs text-slate-400">{data.ai_resolved_conversations} handled by AI</p>
              </Card>

              <Card className="p-5 border-l-4 border-amber-500">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Human Escalations</p>
                <p className="mt-1 text-3xl font-extrabold text-amber-600">{data.human_escalations}</p>
                <p className="mt-1 text-xs text-slate-400">tickets reviewed by agents</p>
              </Card>

              <Card className="p-5 border-l-4 border-violet-500">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Avg AI Confidence</p>
                <p className="mt-1 text-3xl font-extrabold text-violet-600">{(data.average_confidence * 100).toFixed(0)}%</p>
                <p className="mt-1 text-xs text-slate-400">avg latency: {data.average_latency_ms}ms</p>
              </Card>
            </div>

            {/* Breakdowns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top Customer Intents */}
              <Card className="p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-4">Top Detected Intents</h3>
                {data.top_intents.length === 0 ? (
                  <p className="text-xs text-slate-400">No intent traces recorded yet.</p>
                ) : (
                  <div className="space-y-3">
                    {data.top_intents.map((item, idx) => (
                      <div key={idx}>
                        <div className="flex justify-between text-xs font-medium text-slate-700 mb-1">
                          <span>{item.intent}</span>
                          <span>{item.count} inquiries</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2">
                          <div
                            className="bg-indigo-600 h-2 rounded-full"
                            style={{
                              width: `${Math.min(100, Math.max(10, (item.count / (data.total_conversations || 1)) * 100))}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Omnichannel Distribution */}
              <Card className="p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-4">Customer Channel Ingestion</h3>
                <div className="grid grid-cols-2 gap-4 pt-4">
                  <div className="p-4 rounded-lg bg-sky-50 border border-sky-100 text-center">
                    <p className="text-xs font-semibold text-sky-800 uppercase">Telegram Bot</p>
                    <p className="text-2xl font-bold text-sky-900 mt-1">{data.channels.telegram}</p>
                    <p className="text-xs text-sky-600 mt-0.5">active users</p>
                  </div>
                  <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-100 text-center">
                    <p className="text-xs font-semibold text-emerald-800 uppercase">Website Chat</p>
                    <p className="text-2xl font-bold text-emerald-900 mt-1">{data.channels.webchat}</p>
                    <p className="text-xs text-emerald-600 mt-0.5">active visitors</p>
                  </div>
                </div>
              </Card>
            </div>
          </>
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}
