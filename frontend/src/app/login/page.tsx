'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowRight, ArrowLeft, Mail, Lock } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { AxiosError } from 'axios';
import { Logo } from '@/components/layout/Logo';
import { Spinner } from '@/components/ui';
import { CursorGlow, gsap, useGSAP } from '@/components/motion';

function getErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ');
    return err.message;
  }
  return 'An unexpected error occurred.';
}

const inputCls =
  'peer w-full rounded-2xl border border-line bg-fg/[0.04] py-3.5 pl-11 pr-4 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-iris focus:bg-fg/[0.07] focus:ring-4 focus:ring-iris/20';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useGSAP(() => {
    gsap.to('[data-o="1"]', { x: 50, y: 60, duration: 8, repeat: -1, yoyo: true, ease: 'sine.inOut' });
    gsap.to('[data-o="2"]', { x: -40, y: -50, duration: 10, repeat: -1, yoyo: true, ease: 'sine.inOut' });
    gsap.from('[data-line]', { yPercent: 110, duration: 1.1, ease: 'expo.out', stagger: 0.12, delay: 0.2 });
    gsap.from('[data-stat]', { opacity: 0, y: 20, duration: 0.9, ease: 'expo.out', stagger: 0.1, delay: 0.9 });
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      router.replace('/dashboard');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-theme="dark" className="relative grid min-h-screen bg-bg text-slate-900 lg:grid-cols-[1.1fr_1fr]">
      <div className="aurora" aria-hidden><i /></div>
      {/* Brand panel */}
      <div className="relative z-10 hidden overflow-hidden p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-grid [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
        <div data-o="1" className="absolute -left-20 top-20 h-96 w-96 rounded-full bg-indigo-600/50 blur-[110px]" />
        <div data-o="2" className="absolute -right-10 bottom-10 h-96 w-96 rounded-full bg-mint/25 blur-[110px]" />
        <CursorGlow />

        <Link href="/" className="relative flex items-center gap-3">
          <Logo size={40} dark />
          <span className="font-display text-xl font-semibold">
            Cortex<span className="text-mint">CX</span>
          </span>
        </Link>

        <div className="relative">
          <h1 className="font-display text-[5.4rem] leading-[0.92] tracking-[-0.03em]">
            {['Every customer.', 'Remembered.', 'Resolved.'].map((l, i) => (
              <span key={l} className="block overflow-hidden pb-2">
                <span data-line className={`block ${i === 1 ? 'italic text-gradient' : ''}`}>
                  {l}
                </span>
              </span>
            ))}
          </h1>
          <div className="mt-12 grid max-w-md grid-cols-3 gap-4">
            {[
              ['15', 'intents'],
              ['6', 'tools'],
              ['24/7', 'coverage'],
            ].map(([v, l]) => (
              <div key={l} data-stat className="rounded-2xl glass-dark p-4">
                <p className="font-display text-3xl font-semibold">{v}</p>
                <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-slate-400">{l}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative font-mono text-[11px] uppercase tracking-[0.2em] text-slate-500">
          AI Customer Experience OS
        </p>
      </div>

      {/* Form panel */}
      <div className="relative z-10 flex items-center justify-center border-l border-line bg-surface/50 px-6 py-12 backdrop-blur-2xl">
        <Link
          href="/"
          className="absolute left-6 top-6 flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 120, damping: 20, delay: 0.15 }}
          className="w-full max-w-[400px]"
        >
          <div className="mb-8 lg:hidden">
            <Logo size={44} />
          </div>
          <h2 className="font-display text-5xl text-slate-950">Welcome <span className="italic text-gradient-ink">back</span></h2>
          <p className="mt-2 text-slate-500">Sign in to your workspace to continue.</p>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0, x: 0 }}
                animate={{ opacity: 1, height: 'auto', x: [0, -8, 8, -5, 5, 0] }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-6 overflow-hidden rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div className="relative">
              <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 transition-colors peer-focus:text-iris" />
              <input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className={inputCls}
              />
            </div>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 transition-colors peer-focus:text-iris" />
              <input
                id="login-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className={inputCls}
              />
            </div>

            <motion.button
              id="login-submit"
              type="submit"
              disabled={loading}
              whileHover={{ scale: 1.015 }}
              whileTap={{ scale: 0.97 }}
              className="group mt-2 flex w-full items-center justify-center gap-2 rounded-2xl bg-snow py-4 text-sm font-semibold text-ink transition-shadow hover:shadow-glow disabled:opacity-60"
            >
              {loading ? <Spinner size="sm" tone="current" /> : null}
              {loading ? 'Signing in…' : 'Sign in'}
              {!loading && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />}
            </motion.button>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
