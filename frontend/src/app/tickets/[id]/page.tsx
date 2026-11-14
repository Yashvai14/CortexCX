'use client';

import { useCallback, useEffect, useRef, useState, FormEvent } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AnimatePresence, motion } from 'motion/react';
import { ArrowLeft, Lock, MessageSquare, Send, Trash2, CheckCheck, MessagesSquare } from 'lucide-react';
import { AxiosError } from 'axios';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Button, ErrorBanner, Spinner } from '@/components/ui';
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
  addTicketComment,
  deleteTicket,
  getTicket,
  updateTicket,
  type Ticket,
  type TicketPriority,
  type TicketStatus,
  type TicketUpdateRequest,
} from '@/api/tickets';
import { listWorkspaceUsers } from '@/api/workspace';
import { useAuth } from '@/context/AuthContext';
import type { WorkspaceUser } from '@/types';

function errMsg(e: unknown) {
  if (e instanceof AxiosError) {
    const d = e.response?.data?.detail;
    return typeof d === 'string' ? d : e.message;
  }
  return 'Something went wrong';
}

const select =
  'w-full rounded-2xl border border-slate-200 bg-slate-50/60 px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-indigo-500 focus:bg-surface focus:ring-4 focus:ring-indigo-500/15';

function Prop({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[0.14em] text-slate-400">{label}</p>
      {children}
    </div>
  );
}

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const [text, setText] = useState('');
  const [internal, setInternal] = useState(false);
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      setTicket(await getTicket(id));
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
    listWorkspaceUsers().then(setUsers).catch(() => {});
  }, [load]);

  const comments = ticket?.comments?.length ?? 0;
  useEffect(() => {
    if (comments) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [comments]);

  const patch = async (data: TicketUpdateRequest) => {
    setBusy(true);
    setError('');
    try {
      setTicket(await updateTicket(id, data));
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const send = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    try {
      await addTicketComment(id, text.trim(), internal);
      setText('');
      await load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setSending(false);
    }
  };

  const remove = async () => {
    if (!confirm('Delete this ticket permanently? This cannot be undone.')) return;
    try {
      await deleteTicket(id);
      router.replace('/tickets');
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const active = ticket ? ticket.status !== 'resolved' && ticket.status !== 'closed' : false;
  const role = String(user?.role ?? '').toLowerCase();
  const canDelete = role === 'owner' || role === 'admin';

  return (
    <ProtectedRoute>
      <AppLayout title={ticket?.reference ?? 'Ticket'}>
        <Link href="/tickets" className="mb-4 mt-1 inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" /> All tickets
        </Link>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {loading ? (
          <div className="flex justify-center py-24"><Spinner size="lg" /></div>
        ) : !ticket ? null : (
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            {/* Thread */}
            <div className="min-w-0 space-y-5">
              <div className="rounded-3xl border border-slate-200/80 bg-surface/85 p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <TicketStatusBadge status={ticket.status} />
                  <PriorityPill priority={ticket.priority} />
                  <SlaChip due={ticket.due_at} breached={ticket.sla_breached} active={active} />
                  {ticket.category && (
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] text-slate-500">{ticket.category}</span>
                  )}
                </div>
                <h2 className="mt-3 font-display text-3xl font-semibold leading-tight text-slate-950">{ticket.subject}</h2>
                {ticket.description && (
                  <p className="mt-3 whitespace-pre-wrap leading-relaxed text-slate-600">{ticket.description}</p>
                )}
                <p className="mt-4 text-xs text-slate-400">
                  Opened {timeAgo(ticket.created_at)}
                  {ticket.created_by ? ` by ${ticket.created_by.full_name}` : ''}
                </p>
              </div>

              {/* Timeline */}
              <div className="space-y-3">
                <AnimatePresence initial={false}>
                  {ticket.comments?.map((c) =>
                    c.is_event ? (
                      <motion.div
                        key={c.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex items-center gap-3 px-2 text-xs text-slate-400"
                      >
                        <span className="h-px flex-1 bg-slate-200" />
                        <span>{c.content} · {timeAgo(c.created_at)}</span>
                        <span className="h-px flex-1 bg-slate-200" />
                      </motion.div>
                    ) : (
                      <motion.div
                        key={c.id}
                        initial={{ opacity: 0, y: 14, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
                        className={`flex gap-3 rounded-3xl p-4 ${
                          c.is_internal
                            ? 'border border-dashed border-amber-300 bg-amber-50/70'
                            : 'border border-slate-200/80 bg-surface/90'
                        }`}
                      >
                        <Avatar name={c.author?.full_name} size={34} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 text-sm">
                            <span className="font-semibold text-slate-900">{c.author?.full_name ?? 'System'}</span>
                            {c.is_internal && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10.5px] font-medium text-amber-800">
                                <Lock className="h-3 w-3" /> Internal note
                              </span>
                            )}
                            <span className="text-xs text-slate-400">{timeAgo(c.created_at)}</span>
                          </div>
                          <p className="mt-1 whitespace-pre-wrap text-[14.5px] leading-relaxed text-slate-700">{c.content}</p>
                        </div>
                      </motion.div>
                    ),
                  )}
                </AnimatePresence>
                <div ref={endRef} />
              </div>

              {/* Composer */}
              <form
                onSubmit={send}
                className={`rounded-3xl border p-3 transition-colors ${
                  internal ? 'border-amber-300 bg-amber-50/70' : 'border-slate-200/80 bg-surface/90'
                }`}
              >
                <div className="mb-2 flex gap-1 rounded-full bg-slate-900/5 p-1 text-xs font-medium w-fit">
                  {[
                    { v: false, label: 'Reply', Icon: MessageSquare },
                    { v: true, label: 'Internal note', Icon: Lock },
                  ].map(({ v, label, Icon }) => (
                    <button
                      type="button"
                      key={label}
                      onClick={() => setInternal(v)}
                      className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 transition ${
                        internal === v ? 'bg-surface text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                      }`}
                    >
                      <Icon className="h-3.5 w-3.5" /> {label}
                    </button>
                  ))}
                </div>
                <textarea
                  rows={3}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={internal ? 'Only your team can see this…' : 'Write a reply to the customer…'}
                  className="w-full resize-none rounded-2xl bg-transparent px-3 py-2 text-sm outline-none placeholder:text-slate-400"
                />
                <div className="flex justify-end">
                  <Button type="submit" loading={sending} disabled={!text.trim()}>
                    <Send className="h-4 w-4" /> {internal ? 'Add note' : 'Send reply'}
                  </Button>
                </div>
              </form>
            </div>

            {/* Properties */}
            <aside className="space-y-4 lg:sticky lg:top-2 lg:self-start">
              <div className="space-y-5 rounded-3xl border border-slate-200/80 bg-surface/85 p-5">
                <Prop label="Status">
                  <select
                    value={ticket.status}
                    disabled={busy}
                    onChange={(e) => patch({ status: e.target.value as TicketStatus })}
                    className={select}
                  >
                    {STATUSES.map((s) => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
                  </select>
                </Prop>

                <Prop label="Priority">
                  <div className="grid grid-cols-4 gap-1 rounded-2xl bg-slate-100 p-1">
                    {PRIORITIES.slice().reverse().map((p: TicketPriority) => (
                      <button
                        key={p}
                        disabled={busy}
                        onClick={() => patch({ priority: p })}
                        className={`rounded-xl py-1.5 text-[11px] font-medium transition ${
                          ticket.priority === p ? 'bg-surface text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                        }`}
                      >
                        {PRIORITY_META[p].label}
                      </button>
                    ))}
                  </div>
                </Prop>

                <Prop label="Assignee">
                  <select
                    value={ticket.assignee?.id ?? ''}
                    disabled={busy}
                    onChange={(e) =>
                      e.target.value ? patch({ assignee_id: e.target.value }) : patch({ unassign: true })
                    }
                    className={select}
                  >
                    <option value="">Unassigned</option>
                    {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                  </select>
                  {user && ticket.assignee?.id !== user.id && (
                    <button
                      onClick={() => patch({ assignee_id: user.id })}
                      className="mt-2 text-xs font-medium text-indigo-600 hover:underline"
                    >
                      Assign to me
                    </button>
                  )}
                </Prop>

                <Prop label="Customer">
                  {ticket.customer ? (
                    <Link href={`/customers/${ticket.customer.id}`} className="group flex items-center gap-2.5">
                      <Avatar name={ticket.customer.full_name} />
                      <span className="min-w-0 leading-tight">
                        <span className="block truncate text-sm font-medium text-slate-900 group-hover:text-indigo-600">
                          {ticket.customer.full_name}
                        </span>
                        <span className="block truncate text-xs text-slate-400">{ticket.customer.email}</span>
                      </span>
                    </Link>
                  ) : (
                    <p className="text-sm text-slate-400">None linked</p>
                  )}
                </Prop>

                {ticket.conversation_id && (
                  <Link
                    href={`/conversations/${ticket.conversation_id}`}
                    className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:underline"
                  >
                    <MessagesSquare className="h-4 w-4" /> View conversation
                  </Link>
                )}
              </div>

              {active ? (
                <Button className="w-full" variant="secondary" disabled={busy} onClick={() => patch({ status: 'resolved' })}>
                  <CheckCheck className="h-4 w-4" /> Mark resolved
                </Button>
              ) : (
                <Button className="w-full" variant="secondary" disabled={busy} onClick={() => patch({ status: 'open' })}>
                  Reopen ticket
                </Button>
              )}

              <div className="rounded-3xl border border-slate-200/80 bg-surface/60 p-5 text-xs text-slate-500 space-y-1.5">
                <p>First response: {ticket.first_response_at ? timeAgo(ticket.first_response_at) : 'awaiting'}</p>
                <p>Resolved: {ticket.resolved_at ? timeAgo(ticket.resolved_at) : '—'}</p>
              </div>

              {canDelete && (
                <button
                  onClick={remove}
                  className="flex w-full items-center justify-center gap-2 rounded-full py-2 text-xs text-slate-400 transition-colors hover:text-red-600"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete ticket
                </button>
              )}
            </aside>
          </div>
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}
