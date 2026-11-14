'use client';

import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'motion/react';
import { LogOut, Moon, Search, Sun } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/components/theme/ThemeProvider';
import { RoleBadge } from '@/components/ui';
import { OPEN_PALETTE_EVENT } from './CommandPalette';

interface TopNavProps {
  title?: string;
}

export function TopNav({ title }: TopNavProps) {
  const { user, workspace, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  const initials = (user?.full_name ?? '?')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <header className="relative z-10 flex h-[84px] flex-shrink-0 items-center justify-between gap-4 px-6 lg:px-8">
      <div className="min-w-0">
        {workspace && (
          <p className="truncate font-mono text-[10.5px] uppercase tracking-[0.18em] text-slate-400">
            {workspace.slug} <span className="text-slate-300">/</span> {title?.toLowerCase()}
          </p>
        )}
        {title && (
          <motion.h1
            key={title}
            initial={{ opacity: 0, y: 10, filter: 'blur(6px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ duration: 0.5 }}
            className="mt-1 font-display text-[34px] leading-none text-slate-950"
          >
            {title}
          </motion.h1>
        )}
      </div>

      <div className="flex items-center gap-2.5">
        <button
          onClick={() => window.dispatchEvent(new Event(OPEN_PALETTE_EVENT))}
          className="glass hidden w-64 items-center gap-2 rounded-full px-4 py-2.5 text-[13px] text-slate-400 transition-colors hover:text-slate-700 lg:flex"
        >
          <Search className="h-3.5 w-3.5" />
          Search or jump to…
          <kbd className="ml-auto rounded-md bg-fg/5 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">⌘K</kbd>
        </button>

        <motion.button
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.9 }}
          onClick={toggle}
          aria-label="Toggle theme"
          className="glass relative grid h-10 w-10 place-items-center rounded-full text-slate-500 transition-colors hover:text-slate-950"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={theme}
              initial={{ rotate: -90, opacity: 0, scale: 0.5 }}
              animate={{ rotate: 0, opacity: 1, scale: 1 }}
              exit={{ rotate: 90, opacity: 0, scale: 0.5 }}
              transition={{ duration: 0.2 }}
              className="absolute"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </motion.span>
          </AnimatePresence>
        </motion.button>

        {user && (
          <div className="glass flex items-center gap-2.5 rounded-full py-1.5 pl-1.5 pr-4">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-iris to-aqua text-[11px] font-bold text-ink">
              {initials}
            </div>
            <div className="hidden leading-tight sm:block">
              <p className="text-[12.5px] font-semibold text-slate-900">{user.full_name}</p>
              <div className="mt-0.5">{user.role && <RoleBadge role={user.role} />}</div>
            </div>
          </div>
        )}

        <motion.button
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.9 }}
          onClick={handleLogout}
          aria-label="Log out"
          className="glass grid h-10 w-10 place-items-center rounded-full text-slate-500 transition-colors hover:text-slate-950"
        >
          <LogOut className="h-4 w-4" />
        </motion.button>
      </div>
    </header>
  );
}
