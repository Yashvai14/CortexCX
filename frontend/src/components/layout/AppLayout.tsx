'use client';

import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';
import { CommandPalette } from './CommandPalette';
import { Stagger } from '@/components/motion';

interface AppLayoutProps {
  children: React.ReactNode;
  title?: string;
}

export function AppLayout({ children, title }: AppLayoutProps) {
  const pathname = usePathname();
  return (
    <div className="relative flex h-screen overflow-hidden bg-bg">
      <div className="aurora" aria-hidden>
        <i />
      </div>
      <div
        className="pointer-events-none fixed inset-0 z-0 bg-grid-theme [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]"
        aria-hidden
      />
      <Sidebar />
      <div className="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopNav title={title} />
        <main className="flex-1 overflow-y-auto px-6 pb-12 pt-2 lg:px-8">
          <Stagger deps={[pathname]} className="mx-auto max-w-[1400px]">
            {children}
          </Stagger>
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
