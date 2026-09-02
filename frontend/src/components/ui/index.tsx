// Centralised UI primitives — Button, Badge, Spinner, Skeleton, EmptyState, ErrorBanner
import React from 'react';

// ── Button ─────────────────────────────────────────────────────────
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-indigo-600 hover:bg-indigo-700 text-white border-transparent focus:ring-indigo-500',
  secondary:
    'bg-white hover:bg-slate-50 text-slate-700 border-slate-300 focus:ring-slate-400',
  ghost:
    'bg-transparent hover:bg-slate-100 text-slate-600 border-transparent focus:ring-slate-400',
  danger:
    'bg-red-600 hover:bg-red-700 text-white border-transparent focus:ring-red-500',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-sm',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  children,
  className = '',
  ...props
}: ButtonProps) {
  return (
    <button
      className={`
        inline-flex items-center gap-2 font-medium rounded-md border
        transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variantClasses[variant]} ${sizeClasses[size]} ${className}
      `}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      )}
      {children}
    </button>
  );
}

// ── Badge ─────────────────────────────────────────────────────────
type BadgeColor = 'green' | 'red' | 'yellow' | 'blue' | 'slate' | 'indigo' | 'purple';

interface BadgeProps {
  color?: BadgeColor;
  children: React.ReactNode;
}

const badgeColors: Record<BadgeColor, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
  yellow: 'bg-amber-50 text-amber-700 ring-amber-200',
  blue: 'bg-blue-50 text-blue-700 ring-blue-200',
  slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  indigo: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  purple: 'bg-purple-50 text-purple-700 ring-purple-200',
};

export function Badge({ color = 'slate', children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${badgeColors[color]}`}
    >
      {children}
    </span>
  );
}

// ── Spinner ────────────────────────────────────────────────────────
export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const s = size === 'sm' ? 'h-4 w-4' : size === 'lg' ? 'h-8 w-8' : 'h-6 w-6';
  return (
    <svg className={`animate-spin ${s} text-indigo-600`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────
export function SkeletonRow({ cols = 4 }: { cols?: number }) {
  return (
    <div className="animate-pulse flex gap-4 px-4 py-3">
      {Array.from({ length: cols }).map((_, i) => (
        <div key={i} className="h-4 bg-slate-200 rounded flex-1" />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="animate-pulse bg-white rounded-lg border border-slate-200 p-5 space-y-3">
      <div className="h-4 bg-slate-200 rounded w-1/3" />
      <div className="h-3 bg-slate-100 rounded w-2/3" />
      <div className="h-3 bg-slate-100 rounded w-1/2" />
    </div>
  );
}

// ── EmptyState ─────────────────────────────────────────────────────
interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && (
        <div className="mb-4 flex items-center justify-center h-12 w-12 rounded-full bg-slate-100 text-slate-400">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-slate-500 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ── ErrorBanner ────────────────────────────────────────────────────
export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      <strong>Error:</strong> {message}
    </div>
  );
}

// ── Card ───────────────────────────────────────────────────────────
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export function Card({
  children,
  className = '',
  ...props
}: CardProps) {
  return (
    <div
      className={`bg-white border border-slate-200 rounded-lg shadow-xs ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

// ── Status badge helpers ───────────────────────────────────────────
export function ConversationStatusBadge({ status }: { status: string }) {
  const map: Record<string, BadgeColor> = {
    open: 'green',
    pending: 'yellow',
    resolved: 'blue',
    closed: 'slate',
  };
  return <Badge color={map[status] ?? 'slate'}>{status}</Badge>;
}

export function AIStateBadge({ state }: { state: string }) {
  const map: Record<string, BadgeColor> = {
    idle: 'slate',
    processing: 'yellow',
    responded: 'green',
    failed: 'red',
    disabled: 'slate',
  };
  return <Badge color={map[state] ?? 'slate'}>{state}</Badge>;
}

export function DocumentStatusBadge({ status }: { status: string }) {
  const map: Record<string, BadgeColor> = {
    pending: 'yellow',
    chunked: 'blue',
    embedded: 'green',
    failed: 'red',
  };
  return <Badge color={map[status] ?? 'slate'}>{status}</Badge>;
}

export function RoleBadge({ role }: { role: string }) {
  const map: Record<string, BadgeColor> = {
    OWNER: 'purple',
    ADMIN: 'indigo',
    AGENT: 'blue',
  };
  return <Badge color={map[role] ?? 'slate'}>{role}</Badge>;
}

// ── Modal (stub — inline modals used directly in pages) ────────────
export function Modal({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose?: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 relative">
        {onClose && (
          <button onClick={onClose} className="absolute top-3 right-3 text-slate-400 hover:text-slate-700">✕</button>
        )}
        {children}
      </div>
    </div>
  );
}

