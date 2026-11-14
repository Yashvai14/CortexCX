'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'motion/react';
import { CornerDownLeft, LogOut, Moon, Plus, Search, Sun } from 'lucide-react';
import { navItems } from './Sidebar';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/components/theme/ThemeProvider';

interface Cmd {
  id: string;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  run: () => void;
}

export const OPEN_PALETTE_EVENT = 'cortex:palette';

export function CommandPalette() {
  const router = useRouter();
  const { logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [idx, setIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQ('');
    setIdx(0);
  }, []);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === 'Escape') {
        close();
      }
    };
    const openIt = () => setOpen(true);
    window.addEventListener('keydown', key);
    window.addEventListener(OPEN_PALETTE_EVENT, openIt);
    return () => {
      window.removeEventListener('keydown', key);
      window.removeEventListener(OPEN_PALETTE_EVENT, openIt);
    };
  }, [close]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 30);
  }, [open]);

  const commands: Cmd[] = useMemo(
    () => [
      ...navItems.map((n) => ({
        id: n.href,
        label: n.label,
        hint: 'Go to',
        icon: n.icon,
        run: () => router.push(n.href),
      })),
      { id: 'new-ticket', label: 'Create ticket', hint: 'Action', icon: Plus, run: () => router.push('/tickets?new=1') },
      {
        id: 'theme',
        label: theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme',
        hint: 'Action',
        icon: theme === 'dark' ? Sun : Moon,
        run: toggle,
      },
      {
        id: 'logout',
        label: 'Log out',
        hint: 'Action',
        icon: LogOut,
        run: async () => {
          await logout();
          router.push('/login');
        },
      },
    ],
    [router, theme, toggle, logout],
  );

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(needle) || c.hint.toLowerCase().includes(needle));
  }, [commands, q]);

  const choose = (c?: Cmd) => {
    if (!c) return;
    close();
    c.run();
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(results[idx]);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="palette"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={close}
          className="fixed inset-0 z-[60] flex items-start justify-center bg-black/55 px-4 pt-[16vh] backdrop-blur-md"
        >
          <motion.div
            initial={{ opacity: 0, y: -16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
            onClick={(e) => e.stopPropagation()}
            className="edge-glow w-full max-w-xl overflow-hidden rounded-3xl border border-line bg-surface shadow-2xl"
          >
            <div className="flex items-center gap-3 border-b border-line px-5 py-4">
              <Search className="h-4 w-4 text-slate-400" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setIdx(0);
                }}
                onKeyDown={onKey}
                placeholder="Search pages and actions…"
                className="w-full bg-transparent text-[15px] outline-none"
              />
              <kbd className="rounded-md border border-line px-1.5 py-0.5 font-mono text-[10px] text-slate-400">esc</kbd>
            </div>
            <ul className="max-h-[50vh] overflow-y-auto p-2">
              {results.length === 0 && <li className="px-4 py-8 text-center text-sm text-slate-400">Nothing matches “{q}”</li>}
              {results.map((c, i) => {
                const Icon = c.icon;
                const on = i === idx;
                return (
                  <li key={c.id}>
                    <button
                      onMouseEnter={() => setIdx(i)}
                      onClick={() => choose(c)}
                      className={`flex w-full items-center gap-3 rounded-2xl px-3.5 py-3 text-left text-sm transition-colors ${
                        on ? 'bg-fg/[0.07] text-slate-950' : 'text-slate-600'
                      }`}
                    >
                      <span className={`grid h-8 w-8 place-items-center rounded-xl ${on ? 'bg-iris/20 text-iris' : 'bg-fg/5'}`}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="flex-1">{c.label}</span>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400">{c.hint}</span>
                      {on && <CornerDownLeft className="h-3.5 w-3.5 text-slate-400" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
