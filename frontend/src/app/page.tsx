'use client';

import Link from 'next/link';
import { useRef } from 'react';
import { motion } from 'motion/react';
import {
  ArrowUpRight,
  Brain,
  Radar,
  ShieldCheck,
  Workflow,
  Wrench,
  UserRoundCheck,
  Layers,
  Send,
  Globe,
  Gauge,
  Sparkles,
} from 'lucide-react';
import { Logo } from '@/components/layout/Logo';
import {
  CountUp,
  CursorGlow,
  Magnetic,
  ScrollReveal,
  SplitReveal,
  gsap,
  useGSAP,
  useSpotlight,
} from '@/components/motion';
import { useAuth } from '@/context/AuthContext';

const marquee = [
  'Intent detection',
  'Hybrid RAG',
  'Customer memory',
  'Tool planning',
  'Human handoff',
  'Confidence gating',
  'Telegram',
  'Web chat',
  'Learning loop',
  'Live tracing',
];

const pipeline = [
  { n: '01', t: 'Ingest', d: 'Telegram and storefront chat land in one unified inbox.' },
  { n: '02', t: 'Remember', d: 'Episodic memory recalls allergies, sizes and preferences.' },
  { n: '03', t: 'Understand', d: '15 e-commerce intents with entity extraction.' },
  { n: '04', t: 'Plan', d: 'The planner picks tools and retrieval steps for the goal.' },
  { n: '05', t: 'Act', d: 'Orders, stock, coupons, policies and knowledge, called live.' },
  { n: '06', t: 'Gate', d: 'Multi-signal confidence decides: answer or escalate.' },
  { n: '07', t: 'Assist', d: 'Agents get drafts, summaries and memories, not a cold ticket.' },
  { n: '08', t: 'Learn', d: 'Every human correction becomes verified knowledge.' },
];

const tones = {
  light: 'glass border-line',
  dark: 'border-line bg-black/40 text-white',
  brand: 'border-indigo-700 bg-gradient-to-br from-indigo-600 to-indigo-800 text-white',
};

function Bento({
  className = '',
  tone = 'light',
  children,
}: {
  className?: string;
  tone?: keyof typeof tones;
  children: React.ReactNode;
}) {
  const ref = useSpotlight<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={`spotlight group relative overflow-hidden rounded-[28px] border p-7 ${tones[tone]} transition-transform duration-500 hover:-translate-y-1 ${className}`}
    >
      {children}
    </div>
  );
}

function HeroChat() {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const q = gsap.utils.selector(root);
      const tl = gsap.timeline({ repeat: -1, repeatDelay: 2.2, delay: 1.4 });
      tl.set(q('[data-m]'), { opacity: 0, y: 16, scale: 0.96 })
        .set(q('[data-bar]'), { scaleX: 0 })
        .to(q('[data-m="1"]'), { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: 'back.out(1.6)' })
        .to(q('[data-m="2"]'), { opacity: 1, y: 0, scale: 1, duration: 0.45 }, '+=0.5')
        .to(q('[data-bar]'), { scaleX: 1, duration: 1.1, ease: 'power2.inOut', stagger: 0.25 }, '<0.2')
        .to(q('[data-m="3"]'), { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: 'back.out(1.6)' }, '+=0.2')
        .to(q('[data-m="4"]'), { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: 'back.out(1.6)' }, '+=1.1')
        .to(q('[data-m]'), { opacity: 0, y: -10, duration: 0.5, stagger: 0.05 }, '+=3');
    },
    { scope: root },
  );

  return (
    <div ref={root} className="relative mx-auto w-full max-w-[440px]">
      <div className="absolute -inset-6 rounded-[44px] bg-gradient-to-br from-indigo-600/40 via-transparent to-mint/30 blur-3xl" />
      <div className="relative rounded-[32px] glass-dark p-5 shadow-2xl">
        <div className="mb-4 flex items-center gap-3">
          <Logo size={36} dark />
          <div className="leading-tight">
            <p className="text-sm font-semibold text-white">Storefront assistant</p>
            <p className="flex items-center gap-1.5 text-[11px] text-mint">
              <span className="h-1.5 w-1.5 rounded-full bg-mint" /> online · replies in 1.2s
            </p>
          </div>
        </div>

        <div className="space-y-3 text-[13.5px]">
          <div data-m="1" className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-white">
            Where is order #ORD-1042? I also have a nut allergy.
          </div>

          <div data-m="2" className="rounded-2xl rounded-bl-md border border-white/10 bg-white/5 px-4 py-3">
            <p className="mb-2.5 font-mono text-[10px] uppercase tracking-widest text-slate-400">cortex pipeline</p>
            {[
              ['intent · order_tracking', 'bg-indigo-400'],
              ['memory · allergy: nuts', 'bg-volt'],
              ['tool · order_tracking()', 'bg-mint'],
            ].map(([label, color]) => (
              <div key={label} className="mb-2 last:mb-0">
                <div className="mb-1 flex justify-between font-mono text-[10.5px] text-slate-300">
                  <span>{label}</span>
                  <span className="text-slate-500">ok</span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-white/10">
                  <div data-bar className={`h-full origin-left rounded-full ${color}`} />
                </div>
              </div>
            ))}
          </div>

          <div data-m="3" className="w-fit max-w-[88%] rounded-2xl rounded-bl-md bg-snow px-4 py-2.5 text-ink">
            Your order is out for delivery, arriving today by 6 PM. I have noted your nut allergy on the shipment.
          </div>

          <div data-m="4" className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="rounded-full bg-mint/15 px-2 py-0.5 font-medium text-mint">confidence 0.94</span>
            auto-resolved, no human needed
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const { isAuthenticated } = useAuth();
  const root = useRef<HTMLDivElement>(null);
  const pipeLine = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      gsap.from('[data-hero-in]', {
        opacity: 0,
        y: 24,
        duration: 1,
        ease: 'expo.out',
        stagger: 0.12,
        delay: 0.7,
      });
      gsap.from('[data-nav]', { y: -30, opacity: 0, duration: 1, ease: 'expo.out' });

      gsap.to('[data-orb="a"]', { x: 60, y: 40, duration: 9, repeat: -1, yoyo: true, ease: 'sine.inOut' });
      gsap.to('[data-orb="b"]', { x: -50, y: -30, duration: 11, repeat: -1, yoyo: true, ease: 'sine.inOut' });

      // parallax on hero content
      gsap.to('[data-parallax]', {
        yPercent: -14,
        ease: 'none',
        scrollTrigger: { trigger: '[data-hero]', start: 'top top', end: 'bottom top', scrub: true },
      });

      // pipeline line draw + steps
      if (pipeLine.current) {
        gsap.fromTo(
          '[data-pipeline-fill]',
          { scaleY: 0 },
          {
            scaleY: 1,
            ease: 'none',
            scrollTrigger: { trigger: pipeLine.current, start: 'top 70%', end: 'bottom 70%', scrub: 0.6 },
          },
        );
        gsap.utils.toArray<HTMLElement>('[data-step]').forEach((el) => {
          gsap.from(el, {
            opacity: 0,
            x: -30,
            duration: 0.9,
            ease: 'expo.out',
            scrollTrigger: { trigger: el, start: 'top 85%' },
          });
        });
      }

      // big CTA scale
      gsap.from('[data-cta]', {
        scale: 0.92,
        borderRadius: 120,
        ease: 'none',
        scrollTrigger: { trigger: '[data-cta]', start: 'top bottom', end: 'top 40%', scrub: true },
      });
    },
    { scope: root },
  );

  const primary = isAuthenticated ? '/dashboard' : '/login';

  return (
    <div ref={root} data-theme="dark" className="relative overflow-x-clip bg-bg text-slate-900">
      <div className="aurora" aria-hidden><i /></div>
      {/* NAV */}
      <header data-nav className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4">
        <div className="flex w-full max-w-5xl items-center justify-between rounded-full border border-white/10 bg-black/50 py-2 pl-4 pr-2 shadow-xl backdrop-blur-xl">
          <Link href="/" className="flex items-center gap-2.5">
            <Logo size={30} dark />
            <span className="font-display text-[17px] font-semibold text-white">
              Cortex<span className="text-mint">CX</span>
            </span>
          </Link>
          <nav className="hidden items-center gap-8 text-[13px] text-slate-300 md:flex">
            <a href="#pipeline" className="hover:text-white transition-colors">Pipeline</a>
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#numbers" className="hover:text-white transition-colors">Results</a>
          </nav>
          <Link
            href={primary}
            className="rounded-full bg-snow px-5 py-2 text-[13px] font-semibold text-ink transition-transform hover:scale-105 active:scale-95"
          >
            {isAuthenticated ? 'Open dashboard' : 'Sign in'}
          </Link>
        </div>
      </header>

      {/* HERO */}
      <section data-hero className="relative isolate overflow-hidden px-6 pb-28 pt-40 text-white">
        <div className="absolute inset-0 bg-grid [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
        <div data-orb="a" className="absolute -left-32 top-10 h-[480px] w-[480px] rounded-full bg-indigo-600/40 blur-[120px]" />
        <div data-orb="b" className="absolute -right-24 bottom-0 h-[420px] w-[420px] rounded-full bg-mint/25 blur-[120px]" />
        <div className="absolute inset-0 bg-noise opacity-[0.07] mix-blend-overlay" />
        <CursorGlow />

        <div data-parallax className="relative mx-auto grid max-w-6xl items-center gap-16 lg:grid-cols-[1.15fr_1fr]">
          <div>
            <div data-hero-in className="mb-7 inline-flex items-center gap-2 rounded-full glass-dark px-3.5 py-1.5 text-[12px] text-slate-300">
              <Sparkles className="h-3.5 w-3.5 text-volt" />
              The AI operating system for D2C support
            </div>

            <h1 className="font-display text-[clamp(3.2rem,7.6vw,6.8rem)] leading-[0.92] tracking-[-0.03em]">
              <SplitReveal text="Support that" delay={0.2} />
              <br />
              <SplitReveal text="thinks, acts," delay={0.4} wordClassName="italic text-gradient" />
              <br />
              <SplitReveal text="and knows when to hand off." delay={0.6} />
            </h1>

            <p data-hero-in className="mt-8 max-w-xl text-lg leading-relaxed text-slate-400">
              CortexCX remembers every customer, plans the right tools, retrieves with hybrid RAG, and escalates to your
              team only when confidence drops. Not a chatbot. A closed loop.
            </p>

            <div data-hero-in className="mt-10 flex flex-wrap items-center gap-4">
              <Magnetic>
                <Link
                  href={primary}
                  className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-indigo-600 px-7 py-4 text-[15px] font-semibold text-white shadow-glow transition-shadow hover:shadow-[0_10px_60px_-5px_rgb(108_71_255/0.8)]"
                >
                  {isAuthenticated ? 'Open dashboard' : 'Get started'}
                  <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </Link>
              </Magnetic>
              <Link href="/chat" className="rounded-full px-5 py-4 text-[15px] font-medium text-slate-300 transition-colors hover:text-white">
                Try the storefront chat →
              </Link>
            </div>
          </div>

          <div data-hero-in>
            <HeroChat />
          </div>
        </div>
      </section>

      {/* MARQUEE */}
      <div className="overflow-hidden border-y border-line bg-surface/40 py-6 backdrop-blur">
        <div className="flex w-max animate-marquee gap-12 whitespace-nowrap">
          {[...marquee, ...marquee].map((m, i) => (
            <span key={i} className="flex items-center gap-12 font-display text-2xl font-medium text-slate-300">
              {m}
              <span className="h-2 w-2 rounded-full bg-indigo-500" />
            </span>
          ))}
        </div>
      </div>

      {/* PIPELINE */}
      <section id="pipeline" className="mx-auto max-w-6xl px-6 py-32">
        <div className="grid gap-16 lg:grid-cols-[1fr_1.2fr]">
          <div className="lg:sticky lg:top-32 lg:self-start">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-indigo-600">The cognitive pipeline</p>
            <SplitReveal
              as="h2"
              onScroll
              text="Eight steps between a message and a resolved ticket."
              className="mt-4 font-display text-5xl font-semibold leading-[1.02] tracking-tight"
            />
            <ScrollReveal delay={0.2}>
              <p className="mt-6 max-w-md text-slate-500">
                Every inbound message runs the same auditable loop. You can trace each decision, each tool call and each
                confidence score.
              </p>
            </ScrollReveal>
          </div>

          <div ref={pipeLine} className="relative pl-10">
            <div className="absolute bottom-2 left-[11px] top-2 w-px bg-line" />
            <div
              data-pipeline-fill
              className="absolute bottom-2 left-[11px] top-2 w-px origin-top bg-gradient-to-b from-indigo-600 to-mint"
            />
            {pipeline.map((s) => (
              <div key={s.n} data-step className="relative pb-12 last:pb-0">
                <span className="absolute -left-10 top-1 grid h-6 w-6 place-items-center rounded-full border-2 border-iris bg-bg">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-600" />
                </span>
                <p className="font-mono text-xs text-slate-400">{s.n}</p>
                <h3 className="font-display text-3xl font-semibold">{s.t}</h3>
                <p className="mt-1.5 max-w-md text-slate-500">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* BENTO */}
      <section id="features" className="mx-auto max-w-6xl px-6 pb-32">
        <ScrollReveal>
          <h2 className="max-w-2xl font-display text-5xl font-semibold leading-[1.02] tracking-tight">
            Built like infrastructure, <span className="text-gradient-ink">designed like a product.</span>
          </h2>
        </ScrollReveal>

        <div className="mt-14 grid auto-rows-[minmax(230px,auto)] gap-4 md:grid-cols-6">
          <ScrollReveal className="md:col-span-4">
            <Bento className="h-full">
              <Layers className="h-6 w-6 text-indigo-600" />
              <h3 className="mt-5 font-display text-3xl font-semibold">Hybrid RAG that cites its sources</h3>
              <p className="mt-2 max-w-md text-slate-500">
                Dense vectors and BM25 fused with reciprocal rank, reranked and compressed. Untrusted knowledge is fenced
                against prompt injection.
              </p>
              <div className="mt-6 flex flex-wrap gap-2 font-mono text-xs">
                {['dense', 'bm25', 'rrf', 'rerank', 'compress'].map((t, i) => (
                  <span key={t} className="rounded-full bg-fg/10 px-3 py-1 text-slate-900 ring-1 ring-line" style={{ opacity: 1 - i * 0.12 }}>
                    {t}
                  </span>
                ))}
              </div>
            </Bento>
          </ScrollReveal>

          <ScrollReveal delay={0.08} className="md:col-span-2">
            <Bento tone="dark" className="h-full">
              <Gauge className="h-6 w-6 text-mint" />
              <p className="mt-5 font-display text-7xl font-semibold tracking-tight">
                <CountUp value={94} />
                <span className="text-mint">%</span>
              </p>
              <p className="mt-2 text-sm text-slate-400">of routine queries resolved with no human touch.</p>
            </Bento>
          </ScrollReveal>

          <ScrollReveal className="md:col-span-2">
            <Bento className="h-full">
              <Brain className="h-6 w-6 text-indigo-600" />
              <h3 className="mt-5 font-display text-2xl font-semibold">Memory that sticks</h3>
              <p className="mt-2 text-sm text-slate-500">Allergies, sizes and delivery notes, recalled when relevant.</p>
            </Bento>
          </ScrollReveal>

          <ScrollReveal delay={0.08} className="md:col-span-2">
            <Bento className="h-full">
              <Wrench className="h-6 w-6 text-indigo-600" />
              <h3 className="mt-5 font-display text-2xl font-semibold">Real tool calls</h3>
              <p className="mt-2 text-sm text-slate-500">Orders, stock, coupons and policies from your own data.</p>
            </Bento>
          </ScrollReveal>

          <ScrollReveal delay={0.16} className="md:col-span-2">
            <Bento tone="brand" className="h-full">
              <UserRoundCheck className="h-6 w-6 text-volt" />
              <h3 className="mt-5 font-display text-2xl font-semibold">Human handoff, done right</h3>
              <p className="mt-2 text-sm text-indigo-100/80">Agents get drafts, summaries and memories on arrival.</p>
            </Bento>
          </ScrollReveal>

          <ScrollReveal className="md:col-span-3">
            <Bento className="h-full">
              <div className="flex gap-3 text-slate-400">
                <Send className="h-5 w-5" />
                <Globe className="h-5 w-5" />
                <Workflow className="h-5 w-5" />
              </div>
              <h3 className="mt-5 font-display text-2xl font-semibold">Omnichannel by default</h3>
              <p className="mt-2 text-sm text-slate-500">
                Telegram webhooks with dedupe and a guest-aware website widget feed the same brain.
              </p>
            </Bento>
          </ScrollReveal>

          <ScrollReveal delay={0.08} className="md:col-span-3">
            <Bento className="h-full">
              <div className="flex gap-3 text-slate-400">
                <Radar className="h-5 w-5" />
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h3 className="mt-5 font-display text-2xl font-semibold">Local-first, fully traceable</h3>
              <p className="mt-2 text-sm text-slate-500">
                Run on Ollama inside your own stack. Every answer carries its confidence and its trace.
              </p>
            </Bento>
          </ScrollReveal>
        </div>
      </section>

      {/* NUMBERS */}
      <section id="numbers" className="mx-auto max-w-6xl px-6 pb-32">
        <div className="grid gap-10 border-y border-line py-14 text-center md:grid-cols-4">
          {[
            [15, '', 'intent classes'],
            [6, '', 'live commerce tools'],
            [26, '', 'passing backend tests'],
            [2, '', 'channels, one brain'],
          ].map(([v, s, l]) => (
            <ScrollReveal key={String(l)}>
              <p className="font-display text-7xl font-semibold tracking-tight">
                <CountUp value={v as number} />
                {s}
              </p>
              <p className="mt-2 font-mono text-xs uppercase tracking-widest text-slate-500">{l}</p>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 pb-4">
        <div
          data-cta
          className="relative mx-auto max-w-6xl overflow-hidden edge-glow rounded-[56px] bg-surface/60 px-6 py-28 text-center text-white backdrop-blur"
        >
          <div className="absolute inset-0 bg-grid [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" />
          <div className="absolute left-1/2 top-0 h-80 w-[600px] -translate-x-1/2 rounded-full bg-indigo-600/50 blur-[120px]" />
          <h2 className="relative mx-auto max-w-3xl font-display text-6xl font-semibold leading-none tracking-tight">
            Give every customer an <span className="text-gradient">answer, not a queue.</span>
          </h2>
          <div className="relative mt-10">
            <Magnetic>
              <Link
                href={primary}
                className="inline-flex items-center gap-2 rounded-full bg-snow px-8 py-4 text-[15px] font-semibold text-ink"
              >
                {isAuthenticated ? 'Open dashboard' : 'Sign in to CortexCX'}
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </Magnetic>
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl items-center justify-between px-6 py-10 text-sm text-slate-500">
        <span className="flex items-center gap-2">
          <Logo size={22} /> CortexCX
        </span>
        <motion.span whileHover={{ x: 3 }}>AI Customer Experience OS</motion.span>
      </footer>
    </div>
  );
}
