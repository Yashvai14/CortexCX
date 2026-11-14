'use client';

import { Flame, ArrowUp, Minus, ArrowDown, Clock } from 'lucide-react';
import { Badge } from '@/components/ui';
import type { TicketPriority, TicketStatus } from '@/api/tickets';

export const STATUS_META: Record<TicketStatus, { label: string; color: 'green' | 'indigo' | 'yellow' | 'blue' | 'slate' }> = {
  open: { label: 'Open', color: 'green' },
  in_progress: { label: 'In progress', color: 'indigo' },
  waiting: { label: 'Waiting', color: 'yellow' },
  resolved: { label: 'Resolved', color: 'blue' },
  closed: { label: 'Closed', color: 'slate' },
};

export const PRIORITY_META: Record<
  TicketPriority,
  { label: string; bar: string; text: string; bg: string; icon: React.ComponentType<{ className?: string }> }
> = {
  urgent: { label: 'Urgent', bar: 'bg-red-500', text: 'text-red-700', bg: 'bg-red-50', icon: Flame },
  high: { label: 'High', bar: 'bg-orange-500', text: 'text-orange-700', bg: 'bg-orange-50', icon: ArrowUp },
  medium: { label: 'Medium', bar: 'bg-amber-400', text: 'text-amber-700', bg: 'bg-amber-50', icon: Minus },
  low: { label: 'Low', bar: 'bg-slate-300', text: 'text-slate-600', bg: 'bg-slate-100', icon: ArrowDown },
};

export const STATUSES = Object.keys(STATUS_META) as TicketStatus[];
export const PRIORITIES: TicketPriority[] = ['urgent', 'high', 'medium', 'low'];

export function TicketStatusBadge({ status }: { status: TicketStatus }) {
  const m = STATUS_META[status];
  return <Badge color={m.color}>{m.label}</Badge>;
}

export function PriorityPill({ priority }: { priority: TicketPriority }) {
  const m = PRIORITY_META[priority];
  const Icon = m.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${m.bg} ${m.text}`}>
      <Icon className="h-3 w-3" />
      {m.label}
    </span>
  );
}

export function Avatar({ name, size = 28 }: { name?: string | null; size?: number }) {
  const initials = (name ?? '?')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  return (
    <span
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      className="inline-grid flex-shrink-0 place-items-center rounded-full bg-gradient-to-br from-indigo-500 to-mint font-bold text-white"
      title={name ?? 'Unassigned'}
    >
      {initials}
    </span>
  );
}

export function timeAgo(iso: string): string {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function SlaChip({
  due,
  breached,
  active,
}: {
  due: string | null;
  breached: boolean;
  active: boolean;
}) {
  if (!due || !active) return null;
  const ms = new Date(due).getTime() - Date.now();
  const abs = Math.abs(ms);
  const h = Math.floor(abs / 3_600_000);
  const m = Math.floor((abs % 3_600_000) / 60_000);
  const text = h >= 48 ? `${Math.floor(h / 24)}d` : h > 0 ? `${h}h ${m}m` : `${m}m`;
  const soon = !breached && ms < 2 * 3_600_000;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[11px] ${
        breached ? 'bg-red-50 text-red-700' : soon ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'
      }`}
    >
      <Clock className="h-3 w-3" />
      {breached ? `${text} overdue` : `${text} left`}
    </span>
  );
}
