'use client';

import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { RoleBadge } from '@/components/ui';

interface TopNavProps {
  title?: string;
}

export function TopNav({ title }: TopNavProps) {
  const { user, workspace, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  return (
    <header className="h-14 flex-shrink-0 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      {/* Left: page title */}
      <div className="flex items-center gap-3">
        {title && (
          <h1 className="text-base font-semibold text-slate-800">{title}</h1>
        )}
        {workspace && (
          <span className="text-sm text-slate-400 hidden md:block">
            {workspace.slug}
          </span>
        )}
      </div>

      {/* Right: user + logout */}
      <div className="flex items-center gap-4">
        {user && (
          <div className="flex items-center gap-2.5">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-medium text-slate-800 leading-tight">
                {user.full_name}
              </p>
              <p className="text-xs text-slate-400 leading-tight">{user.email}</p>
            </div>
            {user.role && <RoleBadge role={user.role} />}
          </div>
        )}

        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 border border-slate-200 rounded-md px-3 py-1.5 hover:bg-slate-50 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Logout
        </button>
      </div>
    </header>
  );
}
