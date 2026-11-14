'use client';

import { useCallback, useEffect, useState, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Plus, Ticket as TicketIcon } from 'lucide-react';
import { AxiosError } from 'axios';
import { Button, ErrorBanner, Modal } from '@/components/ui';
import {
  PRIORITIES,
  PRIORITY_META,
  TicketStatusBadge,
} from '@/components/tickets/shared';
import {
  createTicket,
  listTickets,
  type Ticket,
  type TicketPriority,
} from '@/api/tickets';

const field =
  'w-full rounded-2xl border border-slate-200 bg-slate-50/60 px-4 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-surface focus:ring-4 focus:ring-indigo-500/15';

interface Props {
  conversationId: string;
  customerId?: string | null;
  defaultSubject?: string;
  defaultDescription?: string;
  defaultPriority?: TicketPriority;
  defaultCategory?: string;
  /** compact = just a button + count, for page headers */
  compact?: boolean;
}

/**
 * Lists tickets linked to a conversation and lets agents raise a new one
 * pre-filled from the conversation / escalation context.
 */
export function LinkedTickets({
  conversationId,
  customerId,
  defaultSubject = '',
  defaultDescription = '',
  defaultPriority = 'medium',
  defaultCategory = '',
  compact = false,
}: Props) {
  const router = useRouter();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState(defaultSubject);
  const [description, setDescription] = useState(defaultDescription);
  const [priority, setPriority] = useState<TicketPriority>(defaultPriority);
  const [category, setCategory] = useState(defaultCategory);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setTickets(await listTickets({ conversation_id: conversationId }));
    } catch {
      /* linked tickets are optional context; ignore load failures */
    }
  }, [conversationId]);

  useEffect(() => {
    load();
  }, [load]);

  const openModal = () => {
    setSubject(defaultSubject);
    setDescription(defaultDescription);
    setPriority(defaultPriority);
    setCategory(defaultCategory);
    setError('');
    setOpen(true);
  };

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
        conversation_id: conversationId,
        customer_id: customerId || undefined,
      });
      setOpen(false);
      router.push(`/tickets/${t.id}`);
    } catch (err) {
      const d = err instanceof AxiosError ? err.response?.data?.detail : null;
      setError(typeof d === 'string' ? d : 'Could not create ticket');
      setSaving(false);
    }
  };

  const activeCount = tickets.filter((t) => t.status !== 'resolved' && t.status !== 'closed').length;

  return (
    <>
      {compact ? (
        <div className="flex flex-wrap items-center gap-2">
          {tickets.map((t) => (
            <Link
              key={t.id}
              href={`/tickets/${t.id}`}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-surface px-3 py-1.5 font-mono text-[11px] text-slate-600 transition-colors hover:border-indigo-300 hover:text-indigo-700"
              title={t.subject}
            >
              <TicketIcon className="h-3 w-3" /> {t.reference}
            </Link>
          ))}
          <Button size="sm" variant="secondary" onClick={openModal}>
            <Plus className="h-3.5 w-3.5" /> Create ticket
          </Button>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200/80 bg-surface/85 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <TicketIcon className="h-4 w-4 text-indigo-600" /> Linked tickets
              {activeCount > 0 && (
                <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] text-indigo-700">{activeCount} active</span>
              )}
            </h3>
            <Button size="sm" variant="secondary" onClick={openModal}>
              <Plus className="h-3.5 w-3.5" /> New
            </Button>
          </div>
          {tickets.length === 0 ? (
            <p className="text-sm text-slate-400">No tickets raised for this conversation.</p>
          ) : (
            <ul className="space-y-2">
              {tickets.map((t) => (
                <li key={t.id}>
                  <Link
                    href={`/tickets/${t.id}`}
                    className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-slate-900/[0.04]"
                  >
                    <span className="min-w-0">
                      <span className="font-mono text-[11px] text-slate-400">{t.reference}</span>
                      <span className="block truncate text-sm font-medium text-slate-900">{t.subject}</span>
                    </span>
                    <TicketStatusBadge status={t.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {open && (
        <Modal onClose={() => setOpen(false)}>
          <h3 className="font-display text-2xl font-semibold text-slate-950">Create ticket</h3>
          <p className="mb-5 mt-1 text-sm text-slate-500">
            Linked to this conversation. Customer and context are carried over.
          </p>
          {error && <div className="mb-3"><ErrorBanner message={error} /></div>}
          <form onSubmit={submit} className="space-y-3">
            <input
              autoFocus
              required
              minLength={3}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Subject"
              className={field}
            />
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Details"
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
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="Category (optional)"
              className={field}
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" loading={saving}>Create ticket</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
