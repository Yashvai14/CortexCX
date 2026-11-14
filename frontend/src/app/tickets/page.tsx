'use client';

import { useCallback, useEffect, useMemo, useState, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'motion/react';
import { Plus, Search, Ticket as TicketIcon } from 'lucide-react';
import { AxiosError } from 'axios';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Button, EmptyState, ErrorBanner, Modal, SkeletonRow } from '@/components/ui';
import { CountUp, useSpotlight } from '@/components/motion';
import {
  Avatar,
  PRIORITIES,
  PRIORITY_META,
  PriorityPill,
  SlaChip,
  STATUS_META,
  STATUSES,
  TicketStatusBadge,
  timeAgo,
} from '@/components/tickets/shared';
import {
  createTicket,
  getTicketStats,
  listTickets,
  type Ticket,
  type TicketFilters,
  type TicketPriority,
  type TicketStats,
  type TicketStatus,
} from '@/api/tickets';
import { listCustomers } from '@/api/customers';
import { listWorkspaceUsers } from '@/api/workspace';
import type { Customer, WorkspaceUser } from '@/types';

type View = 'all' | 'mine' | 'unassigned' | 'overdue';

function errMsg(e: unknown) {
  if (e instanceof AxiosError) {
    const d = e.response?.data?.detail;
    return typeof d === 'string' ? d : e.message;
  }
  return 'Something went wrong';
}

function StatTile({
  label,
  value,
  active,
  onClick,
  tone = 'light',
}: {
  label: string;
  value: number;
  active: boolean;
  onClick: () => void;
  tone?: 'light' | 'danger';
}) {
  const ref = useSpotlight<HTMLButtonElement>();
  return (
    <button
      ref={ref}
      onClick={onClick}
      className={`spotlight relative overflow-hidden rounded-2xl border p-4 text-left transition-all duration-300 hover:-translate-y-0.5 ${
        active
          ? 'border-fg bg-fg text-bg shadow-[0_18px_40px_-18px_rgba(10,10,18,0.6)]'
          : 'border-slate-200/80 bg-surface/85'
      }`}
    >
      <p className={`font-mono text-[10.5px] uppercase tracking-[0.14em] ${active ? 'text-slate-400' : 'text-slate-500'}`}>
        {label}
      </p>
      <p
        className={`mt-2 font-display text-4xl font-semibold leading-none ${
          !active && tone === 'danger' && value > 0 ? 'text-red-600' : ''
        }`}
      >
        <CountUp value={value} duration={0.9} />
      </p>
    </button>
  );
}

export default function TicketsPage() {
  const router = useRouter();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [stats, setStats] = useState<TicketStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [view, setView] = useState<View>('all');
  const [status, setStatus] = useState<TicketStatus | ''>('');
  const [priority, setPriority] = useState<TicketPriority | ''>('');
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [showNew, setShowNew] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('new') === '1') setShowNew(true);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    const filters: TicketFilters = {};
    if (status) filters.status = status;
    if (priority) filters.priority = priority;
    if (view === 'mine') filters.mine = true;
    if (view === 'unassigned') filters.unassigned = true;
    if (debouncedQ.trim()) filters.q = debouncedQ.trim();
    try {
      const [list, st] = await Promise.all([listTickets(filters), getTicketStats()]);
      setTickets(list);
      setStats(st);
      setError('');
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [status, priority, view, debouncedQ]);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(
    () => (view === 'overdue' ? tickets.filter((t) => t.sla_breached) : tickets),
    [tickets, view],
  );

  const pick = (v: View) => setView((cur) => (cur === v ? 'all' : v));

  return (
    <ProtectedRoute>
      <AppLayout title="Tickets">
        <div className="mb-6 mt-2 flex flex-wrap items-end justify-between gap-4">
          <p className="max-w-lg text-slate-500">
            Track every customer issue from first message to resolution, with owners and response deadlines.
          </p>
          <Button size="lg" onClick={() => setShowNew(true)}>
            <Plus className="h-4 w-4" /> New ticket
          </Button>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {/* Stat tiles double as quick filters */}
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="All tickets" value={stats?.total ?? 0} active={view === 'all'} onClick={() => setView('all')} />
          <StatTile label="Assigned to me" value={stats?.assigned_to_me ?? 0} active={view === 'mine'} onClick={() => pick('mine')} />
          <StatTile label="Unassigned" value={stats?.unassigned ?? 0} active={view === 'unassigned'} onClick={() => pick('unassigned')} />
          <StatTile label="Overdue" tone="danger" value={stats?.overdue ?? 0} active={view === 'overdue'} onClick={() => pick('overdue')} />
        </div>

        {/* Toolbar */}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1 rounded-full border border-slate-200/80 bg-surface/80 p-1">
            {(['', ...STATUSES] as (TicketStatus | '')[]).map((s) => {
              const on = status === s;
              return (
                <button
                  key={s || 'all'}
                  onClick={() => setStatus(s)}
                  className={`relative rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors ${
                    on ? 'text-bg' : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {on && (
                    <motion.span
                      layoutId="status-tab"
                      className="absolute inset-0 rounded-full bg-fg"
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                    />
                  )}
                  <span className="relative">
                    {s ? STATUS_META[s].label : 'Any status'}
                    {s && stats ? <span className="ml-1.5 opacity-60">{stats.by_status[s]}</span> : null}
                  </span>
                </button>
              );
            })}
          </div>

          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as TicketPriority | '')}
            className="rounded-full border border-slate-200/80 bg-surface/80 px-4 py-2 text-[13px] text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/15"
          >
            <option value="">Any priority</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>{PRIORITY_META[p].label}</option>
            ))}
          </select>

          <div className="ml-auto flex w-full items-center gap-2 rounded-full border border-slate-200/80 bg-surface/80 px-4 py-2 sm:w-72">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search subject or TCK-1001"
              className="w-full bg-transparent text-[13px] outline-none placeholder:text-slate-400"
            />
          </div>
        </div>

        {/* List */}
        <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-surface/85">
          {loading ? (
            <div className="divide-y divide-slate-100">
              {[1, 2, 3, 4].map((i) => <SkeletonRow key={i} cols={5} />)}
            </div>
          ) : visible.length === 0 ? (
            <EmptyState
              icon={<TicketIcon className="h-5 w-5" />}
              title={tickets.length === 0 && !debouncedQ && !status && !priority && view === 'all' ? 'No tickets yet' : 'No tickets match'}
              description="Create a ticket to start tracking a customer issue."
              action={<Button onClick={() => setShowNew(true)}><Plus className="h-4 w-4" /> New ticket</Button>}
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              <AnimatePresence initial={false}>
                {visible.map((t, i) => {
                  const active = t.status !== 'resolved' && t.status !== 'closed';
                  return (
                    <motion.li
                      key={t.id}
                      layout
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: Math.min(i, 10) * 0.025, type: 'spring', stiffness: 300, damping: 30 }}
                    >
                      <Link
                        href={`/tickets/${t.id}`}
                        className="group relative flex items-center gap-4 px-5 py-4 transition-colors hover:bg-slate-900/[0.03]"
                      >
                        <span className={`absolute left-0 top-3 bottom-3 w-1 rounded-r-full ${PRIORITY_META[t.priority].bar}`} />
                        <div className="min-w-0 flex-1 pl-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[11px] text-slate-400">{t.reference}</span>
                            {t.category && (
                              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10.5px] text-slate-500">{t.category}</span>
                            )}
                          </div>
                          <p className="truncate text-[15px] font-medium text-slate-900 transition-transform group-hover:translate-x-0.5">
                            {t.subject}
                          </p>
                          <p className="mt-0.5 truncate text-xs text-slate-400">
                            {t.customer ? t.customer.full_name : 'No customer'} · opened {timeAgo(t.created_at)}
                          </p>
                        </div>
                        <div className="hidden items-center gap-3 md:flex">
                          <SlaChip due={t.due_at} breached={t.sla_breached} active={active} />
                          <PriorityPill priority={t.priority} />
                          <TicketStatusBadge status={t.status} />
                          <Avatar name={t.assignee?.full_name} />
                        </div>
                      </Link>
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
          )}
        </div>

        {showNew && (
          <NewTicketModal
            onClose={() => setShowNew(false)}
            onCreated={(t) => {
              setShowNew(false);
              router.push(`/tickets/${t.id}`);
            }}
          />
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}

const field =
  'w-full rounded-2xl border border-slate-200 bg-slate-50/60 px-4 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-surface focus:ring-4 focus:ring-indigo-500/15';

function NewTicketModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (t: Ticket) => void;
}) {
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [priority, setPriority] = useState<TicketPriority>('medium');
  const [customerId, setCustomerId] = useState('');
  const [assigneeId, setAssigneeId] = useState('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    listCustomers().then(setCustomers).catch(() => {});
    listWorkspaceUsers().then(setUsers).catch(() => {});
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const t = await createTicket({
        subject,
        description: description || undefined,
        category: category || undefined,
        priority,
        customer_id: customerId || undefined,
        assignee_id: assigneeId || undefined,
      });
      onCreated(t);
    } catch (err) {
      setError(errMsg(err));
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <h3 className="font-display text-2xl font-semibold text-slate-950">New ticket</h3>
      <p className="mb-5 mt-1 text-sm text-slate-500">Response deadline is set from the priority.</p>
      {error && <div className="mb-3"><ErrorBanner message={error} /></div>}
      <form onSubmit={submit} className="space-y-3">
        <input
          autoFocus
          required
          minLength={3}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="What's the issue?"
          className={field}
        />
        <textarea
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Details (optional)"
          className={field}
        />
        <div className="grid grid-cols-4 gap-1.5 rounded-2xl bg-slate-100 p-1">
          {PRIORITIES.slice().reverse().map((p) => (
            <button
              type="button"
              key={p}
              onClick={() => setPriority(p)}
              className={`rounded-xl py-2 text-xs font-medium transition ${
                priority === p ? 'bg-surface text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {PRIORITY_META[p].label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} className={field}>
            <option value="">No customer</option>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}
          </select>
          <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} className={field}>
            <option value="">Unassigned</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
        </div>
        <input
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="Category (e.g. Refund, Shipping)"
          className={field}
        />
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>Create ticket</Button>
        </div>
      </form>
    </Modal>
  );
}
