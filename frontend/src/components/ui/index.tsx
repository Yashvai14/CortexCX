'use client';

// Centralised UI primitives — Button, Badge, Spinner, Skeleton, EmptyState, ErrorBanner, Card, Modal
import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, AlertTriangle } from 'lucide-react';

// ── Button ─────────────────────────────────────────────────────────
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onDrag' | 'onDragStart' | 'onDragEnd' | 'onAnimationStart'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-fg text-bg border-transparent hover:bg-indigo-500 hover:text-snow hover:shadow-glow focus-visible:ring-indigo-400',
  secondary:
    'glass text-slate-800 hover:text-slate-950 hover:border-line-strong focus-visible:ring-slate-400',
  ghost:
    'bg-transparent hover:bg-fg/5 text-slate-600 hover:text-slate-900 border-transparent focus-visible:ring-slate-400',
  danger:
    'bg-red-500/90 hover:bg-red-500 text-snow border-transparent focus-visible:ring-red-400',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3.5 py-1.5 text-xs',
  md: 'px-4.5 py-2 text-sm',
  lg: 'px-6 py-2.5 text-sm',
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
  const off = disabled || loading;
  return (
    <motion.button
      whileHover={off ? undefined : { y: -1 }}
      whileTap={off ? undefined : { scale: 0.96 }}
      transition={{ type: 'spring', stiffness: 500, damping: 28 }}
      className={`inline-flex items-center justify-center gap-2 font-medium rounded-full border
        transition-[background,border-color,box-shadow,color] duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={off}
      {...(props as React.ComponentProps<typeof motion.button>)}
    >
      {loading && <Spinner size="sm" tone="current" />}
      {children}
    </motion.button>
  );
}

// ── Badge ─────────────────────────────────────────────────────────
type BadgeColor = 'green' | 'red' | 'yellow' | 'blue' | 'slate' | 'indigo' | 'purple';
type BadgeVariant = 'success' | 'danger' | 'warning' | 'info' | 'default' | BadgeColor;

interface BadgeProps {
  color?: BadgeColor;
  variant?: BadgeVariant;
  className?: string;
  children: React.ReactNode;
}

// Shade tokens are themed (see globals.css), so these read correctly in light and dark.
const badgeColors: Record<BadgeColor, { wrap: string; dot: string }> = {
  green: { wrap: 'bg-emerald-50 text-emerald-700 ring-emerald-200', dot: 'bg-emerald-500' },
  red: { wrap: 'bg-red-50 text-red-700 ring-red-200', dot: 'bg-red-500' },
  yellow: { wrap: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
  blue: { wrap: 'bg-sky-50 text-sky-700 ring-sky-200', dot: 'bg-sky-500' },
  slate: { wrap: 'bg-slate-100 text-slate-600 ring-slate-200', dot: 'bg-slate-400' },
  indigo: { wrap: 'bg-indigo-50 text-indigo-700 ring-indigo-200', dot: 'bg-indigo-500' },
  purple: { wrap: 'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200', dot: 'bg-fuchsia-500' },
};

const variantToColor: Record<string, BadgeColor> = {
  success: 'green',
  danger: 'red',
  warning: 'yellow',
  info: 'blue',
  default: 'slate',
};

export function Badge({ color, variant, className = '', children }: BadgeProps) {
  const resolvedColor: BadgeColor =
    color ?? (variant && variantToColor[variant] ? variantToColor[variant] : (variant as BadgeColor) ?? 'slate');
  const c = badgeColors[resolvedColor] || badgeColors.slate;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full pl-2 pr-2.5 py-0.5 text-[11px] font-medium capitalize ring-1 ring-inset ${c.wrap} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {children}
    </span>
  );
}

// ── Spinner ────────────────────────────────────────────────────────
export function Spinner({
  size = 'md',
  tone = 'brand',
}: {
  size?: 'sm' | 'md' | 'lg';
  tone?: 'brand' | 'current';
}) {
  const s = size === 'sm' ? 'h-3.5 w-3.5' : size === 'lg' ? 'h-8 w-8' : 'h-5 w-5';
  return (
    <svg
      className={`animate-spin ${s} ${tone === 'brand' ? 'text-indigo-400' : ''}`}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-90" stroke="currentColor" strokeWidth="3" strokeLinecap="round" d="M22 12a10 10 0 00-10-10" />
    </svg>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────
const shimmer =
  'bg-[linear-gradient(90deg,var(--color-slate-100),var(--color-slate-200),var(--color-slate-100))] bg-[length:200%_100%] animate-shimmer';

export function SkeletonRow({ cols = 4 }: { cols?: number }) {
  return (
    <div className="flex gap-4 px-4 py-3">
      {Array.from({ length: cols }).map((_, i) => (
        <div key={i} className={`h-4 rounded-full flex-1 ${shimmer}`} />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="glass rounded-3xl p-6 space-y-3">
      <div className={`h-3 rounded-full w-1/3 ${shimmer}`} />
      <div className={`h-10 rounded-xl w-1/2 ${shimmer}`} />
      <div className={`h-3 rounded-full w-2/3 ${shimmer}`} />
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
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 text-center"
    >
      {icon && (
        <div className="relative mb-5">
          <span className="absolute inset-0 rounded-2xl bg-indigo-500/30 animate-pulse-ring" />
          <div className="relative flex items-center justify-center h-12 w-12 rounded-2xl bg-fg text-bg">
            {icon}
          </div>
        </div>
      )}
      <h3 className="font-display text-2xl text-slate-900">{title}</h3>
      {description && <p className="mt-1 text-sm text-slate-500 max-w-sm">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </motion.div>
  );
}

// ── ErrorBanner ────────────────────────────────────────────────────
export function ErrorBanner({ message }: { message: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-2.5 rounded-2xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
    >
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
      <span>{message}</span>
    </motion.div>
  );
}

// ── Card ───────────────────────────────────────────────────────────
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className = '', ...props }: CardProps) {
  return (
    <div
      className={`glass rounded-3xl transition-[box-shadow,border-color] duration-300 hover:border-line-strong ${className}`}
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
    processing: 'yellow',
    completed: 'green',
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
  return <Badge color={map[role.toUpperCase()] ?? 'slate'}>{role.toLowerCase()}</Badge>;
}

// ── Modal ──────────────────────────────────────────────────────────
export function Modal({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose?: () => void;
}) {
  return (
    <AnimatePresence>
      <motion.div
        key="overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-50 p-4"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 24 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 12 }}
          transition={{ type: 'spring', stiffness: 380, damping: 30 }}
          onClick={(e) => e.stopPropagation()}
          className="edge-glow bg-surface rounded-[28px] shadow-2xl w-full max-w-md p-7 relative border border-line"
        >
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close"
              className="absolute top-4 right-4 h-8 w-8 grid place-items-center rounded-full text-slate-400 hover:text-slate-900 hover:bg-fg/10 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          {children}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
