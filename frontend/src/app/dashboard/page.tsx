'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, Bot, MessagesSquare, Radio, Ticket as TicketIcon, Users } from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Card, SkeletonCard, ConversationStatusBadge, AIStateBadge, ErrorBanner } from '@/components/ui';
import { CountUp, gsap, useGSAP, useSpotlight } from '@/components/motion';
import { useAuth } from '@/context/AuthContext';
import { listCustomers } from '@/api/customers';
import { listConversations } from '@/api/conversations';
import { getTicketStats, type TicketStats } from '@/api/tickets';
import type { Customer, Conversation } from '@/types';
import { AxiosError } from 'axios';

/* ── Stat tile ─────────────────────────────────────────────────── */
function StatTile({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  sub: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}) {
  const ref = useSpotlight<HTMLDivElement>();
  return (
    <div ref={ref} className="spotlight glass group relative overflow-hidden rounded-3xl p-6 transition-transform duration-500 hover:-translate-y-1">
      <div className="flex items-start justify-between">
        <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
        <span className={`grid h-9 w-9 place-items-center rounded-xl transition-transform duration-500 group-hover:rotate-12 ${accent}`}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-6 font-display text-7xl leading-none text-slate-950">
        <CountUp value={value} />
      </p>
      <p className="mt-3 text-xs text-slate-400">{sub}</p>
    </div>
  );
}

/* ── 14-day volume chart (real data from conversations) ────────── */
function VolumeChart({ conversations }: { conversations: Conversation[] }) {
  const root = useRef<SVGSVGElement>(null);
  const days = 14;
  const series = useMemo(() => {
    const now = new Date();
    const buckets = Array.from({ length: days }, (_, i) => {
      const d = new Date(now);
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - (days - 1 - i));
      return { day: d, count: 0 };
    });
    conversations.forEach((c) => {
      const t = new Date(c.created_at);
      t.setHours(0, 0, 0, 0);
      const b = buckets.find((x) => x.day.getTime() === t.getTime());
      if (b) b.count += 1;
    });
    return buckets;
  }, [conversations]);

  const W = 640;
  const H = 180;
  const pad = 8;
  const max = Math.max(3, ...series.map((s) => s.count));
  const pts = series.map((s, i) => [pad + (i * (W - pad * 2)) / (days - 1), H - pad - (s.count / max) * (H - pad * 2 - 14)] as const);
  const line = pts.reduce((acc, [x, y], i) => {
    if (i === 0) return `M ${x} ${y}`;
    const [px, py] = pts[i - 1];
    const cx = (px + x) / 2;
    return `${acc} C ${cx} ${py}, ${cx} ${y}, ${x} ${y}`;
  }, '');
  const area = `${line} L ${pts[pts.length - 1][0]} ${H} L ${pts[0][0]} ${H} Z`;
  const total = series.reduce((a, b) => a + b.count, 0);

  useGSAP(
    () => {
      const path = root.current?.querySelector<SVGPathElement>('[data-line]');
      if (!path) return;
      const len = path.getTotalLength();
      gsap.fromTo(path, { strokeDasharray: len, strokeDashoffset: len }, { strokeDashoffset: 0, duration: 1.6, ease: 'power3.out' });
      gsap.fromTo('[data-area]', { opacity: 0 }, { opacity: 1, duration: 1.2, delay: 0.5 });
      gsap.fromTo('[data-dot]', { scale: 0, transformOrigin: 'center' }, { scale: 1, duration: 0.5, delay: 1.3, stagger: 0.04, ease: 'back.out(3)' });
    },
    { scope: root, dependencies: [total] },
  );

  return (
    <div>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-slate-500">Conversation volume · 14 days</p>
          <p className="mt-2 font-display text-5xl leading-none text-slate-950">
            <CountUp value={total} /> <span className="text-xl italic text-slate-400">new</span>
          </p>
        </div>
        <span className="rounded-full bg-aqua/15 px-3 py-1 font-mono text-[11px] text-emerald-700 dark:text-aqua">live</span>
      </div>
      <svg ref={root} viewBox={`0 0 ${W} ${H}`} className="h-44 w-full overflow-visible" preserveAspectRatio="none">
        <defs>
          <linearGradient id="vol-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b7bff" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#8b7bff" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="vol-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#8b7bff" />
            <stop offset="100%" stopColor="#5ef2d0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1="0" x2={W} y1={H * g} y2={H * g} stroke="var(--line)" strokeDasharray="3 6" />
        ))}
        <path data-area d={area} fill="url(#vol-fill)" />
        <path data-line d={line} fill="none" stroke="url(#vol-line)" strokeWidth="2.5" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        {pts.map(([x, y], i) =>
          series[i].count > 0 ? <circle key={i} data-dot cx={x} cy={y} r="3.5" fill="var(--bg)" stroke="#5ef2d0" strokeWidth="2" vectorEffect="non-scaling-stroke" /> : null,
        )}
      </svg>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-slate-400">
        <span>{series[0].day.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
        <span>today</span>
      </div>
    </div>
  );
}

/* ── AI share ring ─────────────────────────────────────────────── */
function Ring({ pct }: { pct: number }) {
  const root = useRef<SVGSVGElement>(null);
  const r = 54;
  const c = 2 * Math.PI * r;
  useGSAP(
    () => {
      gsap.fromTo('[data-ring]', { strokeDashoffset: c }, { strokeDashoffset: c * (1 - pct / 100), duration: 1.6, ease: 'power3.out' });
    },
    { scope: root, dependencies: [pct] },
  );
  return (
    <div className="relative mx-auto h-40 w-40">
      <svg ref={root} viewBox="0 0 128 128" className="h-full w-full -rotate-90">
        <defs>
          <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#8b7bff" />
            <stop offset="100%" stopColor="#5ef2d0" />
          </linearGradient>
        </defs>
        <circle cx="64" cy="64" r={r} fill="none" stroke="var(--line)" strokeWidth="9" />
        <circle data-ring cx="64" cy="64" r={r} fill="none" stroke="url(#ring)" strokeWidth="9" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="font-display text-5xl leading-none text-slate-950">
            <CountUp value={pct} />
            <span className="text-2xl text-aqua">%</span>
          </p>
          <p className="mt-1 font-mono text-[9.5px] uppercase tracking-[0.16em] text-slate-400">AI handled</p>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [tickets, setTickets] = useState<TicketStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [c, cv, tk] = await Promise.all([
          listCustomers(),
          listConversations(),
          getTicketStats().catch(() => null),
        ]);
        setCustomers(c);
        setConversations(cv);
        setTickets(tk);
      } catch (err) {
        setError(err instanceof AxiosError ? err.response?.data?.detail ?? err.message : 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const open = conversations.filter((c) => c.status === 'open');
  const ai = conversations.filter((c) => c.ai_enabled);
  const aiShare = conversations.length ? Math.round((ai.length / conversations.length) * 100) : 0;
  const recent = [...conversations].sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at)).slice(0, 5);
  const newest = [...customers].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at)).slice(0, 5);
  const first = user?.full_name?.split(' ')[0] ?? 'there';

  return (
    <ProtectedRoute>
      <AppLayout title="Dashboard">
        {/* Hero greeting */}
        <div className="mb-10 mt-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-600 dark:text-aqua">Good {getTimeOfDay()}</p>
          <h2 className="mt-3 font-display text-[clamp(3rem,7vw,5.6rem)] leading-[0.95] text-slate-950">
            Hello, <span className="italic text-gradient-ink">{first}</span>
          </h2>
          <p className="mt-4 max-w-xl text-[15px] text-slate-500">
            {loading
              ? 'Gathering your workspace…'
              : `${open.length} open conversation${open.length === 1 ? '' : 's'}, with AI handling ${aiShare}% of them.`}
          </p>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {loading ? (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
          </div>
        ) : (
          <>
            {/* Bento: chart + ring + tickets */}
            <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-6">
              <Card className="edge-glow p-6 lg:col-span-4">
                <VolumeChart conversations={conversations} />
              </Card>
              <div className="grid gap-4 lg:col-span-2">
                <Card className="p-6">
                  <Ring pct={aiShare} />
                </Card>
              </div>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatTile label="Customers" value={customers.length} sub="across workspace" icon={Users} accent="bg-iris/15 text-iris" />
              <StatTile label="Conversations" value={conversations.length} sub="all time" icon={MessagesSquare} accent="bg-aqua/15 text-aqua" />
              <StatTile label="Open now" value={open.length} sub="currently active" icon={Radio} accent="bg-peach/15 text-peach" />
              <StatTile label="AI-enabled" value={ai.length} sub="AI handling replies" icon={Bot} accent="bg-rose-glow/15 text-rose-glow" />
            </div>

            {/* Tickets strip */}
            {tickets && (
              <Link href="/tickets" className="spotlight glass group mb-8 flex flex-wrap items-center gap-x-10 gap-y-3 rounded-3xl px-6 py-5 transition-transform duration-500 hover:-translate-y-0.5">
                <span className="flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-iris/15 text-iris"><TicketIcon className="h-4 w-4" /></span>
                  <span className="font-display text-2xl text-slate-950">Tickets</span>
                </span>
                {[
                  ['open', tickets.by_status.open + tickets.by_status.in_progress + tickets.by_status.waiting],
                  ['unassigned', tickets.unassigned],
                  ['overdue', tickets.overdue],
                  ['assigned to me', tickets.assigned_to_me],
                ].map(([label, n]) => (
                  <span key={label as string} className="flex items-baseline gap-2">
                    <span className={`font-display text-4xl leading-none ${label === 'overdue' && (n as number) > 0 ? 'text-red-600' : 'text-slate-950'}`}>
                      <CountUp value={n as number} duration={0.8} />
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">{label}</span>
                  </span>
                ))}
                <ArrowUpRight className="ml-auto h-5 w-5 text-slate-400 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-iris" />
              </Link>
            )}

            {/* Lists */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card className="overflow-hidden">
                <div className="flex items-center justify-between px-6 pb-2 pt-5">
                  <h3 className="font-display text-3xl text-slate-950">Recent conversations</h3>
                  <Link href="/conversations" className="group inline-flex items-center gap-1 text-xs font-medium text-indigo-600">
                    View all <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  </Link>
                </div>
                <div className="px-3 pb-3">
                  {recent.length === 0 ? (
                    <p className="px-5 py-8 text-center text-sm text-slate-400">No conversations yet</p>
                  ) : (
                    recent.map((conv) => (
                      <Link key={conv.id} href={`/conversations/${conv.id}`} className="group flex items-center justify-between rounded-2xl px-3 py-3 transition-colors hover:bg-fg/[0.05]">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900 transition-transform group-hover:translate-x-0.5">{conv.subject}</p>
                          <p className="mt-0.5 text-xs text-slate-400">{formatDate(conv.updated_at)}</p>
                        </div>
                        <div className="ml-3 flex flex-shrink-0 items-center gap-2">
                          <AIStateBadge state={conv.ai_state} />
                          <ConversationStatusBadge status={conv.status} />
                        </div>
                      </Link>
                    ))
                  )}
                </div>
              </Card>

              <Card className="overflow-hidden">
                <div className="flex items-center justify-between px-6 pb-2 pt-5">
                  <h3 className="font-display text-3xl text-slate-950">New customers</h3>
                  <Link href="/customers" className="group inline-flex items-center gap-1 text-xs font-medium text-indigo-600">
                    View all <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  </Link>
                </div>
                <div className="px-3 pb-3">
                  {newest.length === 0 ? (
                    <p className="px-5 py-8 text-center text-sm text-slate-400">No customers yet</p>
                  ) : (
                    newest.map((cust) => (
                      <Link key={cust.id} href={`/customers/${cust.id}`} className="group flex items-center gap-3 rounded-2xl px-3 py-3 transition-colors hover:bg-fg/[0.05]">
                        <div className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-full bg-gradient-to-br from-iris to-aqua text-xs font-bold text-ink">
                          {cust.full_name?.[0]?.toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-slate-900">{cust.full_name}</p>
                          <p className="mt-0.5 truncate text-xs text-slate-400">{cust.email}</p>
                        </div>
                        <p className="flex-shrink-0 text-xs text-slate-400">{formatDate(cust.created_at)}</p>
                      </Link>
                    ))
                  )}
                </div>
              </Card>
            </div>
          </>
        )}
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
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
