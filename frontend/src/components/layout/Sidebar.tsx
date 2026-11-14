'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'motion/react';
import {
  LayoutDashboard,
  MessagesSquare,
  LifeBuoy,
  BarChart3,
  ShoppingBag,
  Users,
  BookOpen,
  MessageCircle,
  Settings,
  Ticket,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Logo } from './Logo';

export const navGroups = [
  {
    label: 'Overview',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
      { label: 'Analytics', href: '/analytics', icon: BarChart3 },
    ],
  },
  {
    label: 'Support',
    items: [
      { label: 'Conversations', href: '/conversations', icon: MessagesSquare },
      { label: 'Tickets', href: '/tickets', icon: Ticket },
      { label: 'Human Handoff', href: '/escalations', icon: LifeBuoy },
      { label: 'Customers', href: '/customers', icon: Users },
    ],
  },
  {
    label: 'Brain',
    items: [
      { label: 'Knowledge Base', href: '/knowledge', icon: BookOpen },
      { label: 'Commerce & Ops', href: '/commerce', icon: ShoppingBag },
      { label: 'Storefront Chat', href: '/chat', icon: MessageCircle },
    ],
  },
];

export const navItems = [...navGroups.flatMap((g) => g.items), { label: 'Settings', href: '/settings', icon: Settings }];

function NavLink({ item, active }: { item: (typeof navItems)[number]; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={`group relative flex items-center gap-3 rounded-2xl px-3.5 py-2.5 text-[13.5px] font-medium transition-colors ${
        active ? 'text-slate-950' : 'text-slate-500 hover:text-slate-900'
      }`}
    >
      {active && (
        <motion.span
          layoutId="nav-pill"
          className="edge-glow absolute inset-0 rounded-2xl bg-fg/[0.07]"
          transition={{ type: 'spring', stiffness: 420, damping: 34 }}
        />
      )}
      <span className="relative grid h-7 w-7 place-items-center">
        <Icon
          className={`h-[17px] w-[17px] transition-transform duration-300 group-hover:scale-110 ${active ? 'text-iris' : ''}`}
          strokeWidth={1.8}
        />
      </span>
      <span className="relative">{item.label}</span>
      {active && (
        <motion.span
          layoutId="nav-dot"
          className="relative ml-auto h-1.5 w-1.5 rounded-full bg-aqua shadow-[0_0_12px_var(--color-aqua)]"
        />
      )}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { workspace } = useAuth();
  const isActive = (href: string) => (href === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(href));

  return (
    <aside className="relative z-10 hidden h-screen w-[268px] flex-shrink-0 p-3 md:flex">
      <div className="glass relative flex w-full flex-col overflow-hidden rounded-[28px]">
        <div className="pointer-events-none absolute -left-16 -top-20 h-56 w-56 rounded-full bg-iris/25 blur-3xl" />

        <Link href="/dashboard" className="relative flex items-center gap-3 px-5 pb-4 pt-6">
          <motion.div whileHover={{ rotate: -10, scale: 1.08 }} transition={{ type: 'spring', stiffness: 400, damping: 14 }}>
            <Logo size={38} />
          </motion.div>
          <div className="min-w-0">
            <p className="font-display text-[22px] leading-none text-slate-950">
              Cortex<span className="italic text-aqua">CX</span>
            </p>
            {workspace && (
              <p className="mt-1 max-w-[140px] truncate font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400">
                {workspace.name}
              </p>
            )}
          </div>
        </Link>

        <nav className="relative flex-1 space-y-5 overflow-y-auto px-3 pb-3 pt-2">
          {navGroups.map((g) => (
            <div key={g.label}>
              <p className="mb-1.5 px-3.5 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-400">{g.label}</p>
              <div className="space-y-0.5">
                {g.items.map((item) => (
                  <NavLink key={item.href} item={item} active={isActive(item.href)} />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="relative space-y-2 p-3">
          <NavLink item={navItems[navItems.length - 1]} active={isActive('/settings')} />
          <div className="rounded-2xl border border-line bg-fg/[0.03] p-3.5">
            <div className="flex items-center gap-2 text-[12px] font-medium text-slate-900">
              <Sparkles className="h-3.5 w-3.5 text-volt" />
              AI engine live
              <span className="relative ml-auto flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-aqua" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-aqua" />
              </span>
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">RAG, memory and tool planning running.</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
