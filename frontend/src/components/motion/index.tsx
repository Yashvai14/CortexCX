'use client';

import { useRef, useEffect, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(useGSAP, ScrollTrigger);

export { gsap, ScrollTrigger, useGSAP };

const reduced = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Staggered entrance for every direct child of the container. Re-runs on `deps`. */
export function Stagger({
  children,
  className = '',
  y = 22,
  delay = 0,
  deps = [],
}: {
  children: React.ReactNode;
  className?: string;
  y?: number;
  delay?: number;
  deps?: unknown[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      if (reduced() || !ref.current) return;
      gsap.fromTo(
        ref.current.children,
        { opacity: 0, y, filter: 'blur(6px)' },
        {
          opacity: 1,
          y: 0,
          filter: 'blur(0px)',
          duration: 0.8,
          ease: 'expo.out',
          stagger: 0.07,
          delay,
          clearProps: 'filter,transform',
        },
      );
    },
    { scope: ref, dependencies: deps },
  );
  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}

/** Count a number up from 0 when mounted. */
export function CountUp({
  value,
  duration = 1.4,
  className = '',
}: {
  value: number;
  duration?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(
    () => {
      if (!ref.current) return;
      if (reduced()) {
        ref.current.textContent = String(value);
        return;
      }
      const o = { v: 0 };
      gsap.to(o, {
        v: value,
        duration,
        ease: 'power3.out',
        onUpdate: () => {
          if (ref.current) ref.current.textContent = Math.round(o.v).toLocaleString();
        },
      });
    },
    { dependencies: [value] },
  );
  return (
    <span ref={ref} className={className}>
      0
    </span>
  );
}

/** Split text into words that rise in, optionally on scroll. */
export function SplitReveal({
  text,
  className = '',
  as: Tag = 'span',
  delay = 0,
  onScroll = false,
  wordClassName = '',
}: {
  wordClassName?: string;
  text: string;
  className?: string;
  as?: 'span' | 'h1' | 'h2' | 'h3' | 'p';
  delay?: number;
  onScroll?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  useGSAP(
    () => {
      if (!ref.current || reduced()) return;
      const words = ref.current.querySelectorAll('[data-w]');
      gsap.fromTo(
        words,
        { yPercent: 115, rotate: 4, opacity: 0 },
        {
          yPercent: 0,
          rotate: 0,
          opacity: 1,
          duration: 1,
          ease: 'expo.out',
          stagger: 0.045,
          delay,
          scrollTrigger: onScroll
            ? { trigger: ref.current, start: 'top 85%' }
            : undefined,
        },
      );
    },
    { scope: ref },
  );
  const Comp = Tag as React.ElementType;
  return (
    <Comp ref={ref} className={className} aria-label={text}>
      {text.split(' ').map((w, i) => (
        <span key={i} className="inline-block overflow-hidden align-bottom pb-[0.12em] -mb-[0.12em]" aria-hidden>
          <span data-w className={`inline-block will-change-transform ${wordClassName}`}>
            {w}
            {' '}
          </span>
        </span>
      ))}
    </Comp>
  );
}

/** Fade/slide a block in when it scrolls into view. */
export function ScrollReveal({
  children,
  className = '',
  y = 40,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  y?: number;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      if (!ref.current || reduced()) {
        if (ref.current) ref.current.style.opacity = '1';
        return;
      }
      gsap.fromTo(
        ref.current,
        { opacity: 0, y },
        {
          opacity: 1,
          y: 0,
          duration: 1,
          delay,
          ease: 'expo.out',
          scrollTrigger: { trigger: ref.current, start: 'top 88%' },
        },
      );
    },
    { scope: ref },
  );
  return (
    <div ref={ref} data-reveal className={className}>
      {children}
    </div>
  );
}

/** Button/element that is gently pulled toward the cursor. */
export function Magnetic({
  children,
  strength = 0.35,
  className = '',
}: {
  children: React.ReactNode;
  strength?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced()) return;
    const xTo = gsap.quickTo(el, 'x', { duration: 0.6, ease: 'elastic.out(1,0.5)' });
    const yTo = gsap.quickTo(el, 'y', { duration: 0.6, ease: 'elastic.out(1,0.5)' });
    const move = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      xTo((e.clientX - (r.left + r.width / 2)) * strength);
      yTo((e.clientY - (r.top + r.height / 2)) * strength);
    };
    const leave = () => {
      xTo(0);
      yTo(0);
    };
    el.addEventListener('mousemove', move);
    el.addEventListener('mouseleave', leave);
    return () => {
      el.removeEventListener('mousemove', move);
      el.removeEventListener('mouseleave', leave);
    };
  }, [strength]);
  return (
    <div ref={ref} className={`inline-block ${className}`}>
      {children}
    </div>
  );
}

/** Sets --mx/--my on hover so `.spotlight` cards glow under the cursor. */
export function useSpotlight<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const move = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty('--mx', `${e.clientX - r.left}px`);
      el.style.setProperty('--my', `${e.clientY - r.top}px`);
    };
    el.addEventListener('mousemove', move);
    return () => el.removeEventListener('mousemove', move);
  }, []);
  return ref;
}

/** Large soft cursor glow for dark hero sections. */
export function CursorGlow({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [ok, setOk] = useState(false);
  useEffect(() => {
    setOk(!reduced());
  }, []);
  useEffect(() => {
    if (!ok || !ref.current) return;
    const el = ref.current;
    const parent = el.parentElement!;
    const xTo = gsap.quickTo(el, 'x', { duration: 0.9, ease: 'power3.out' });
    const yTo = gsap.quickTo(el, 'y', { duration: 0.9, ease: 'power3.out' });
    const move = (e: MouseEvent) => {
      const r = parent.getBoundingClientRect();
      xTo(e.clientX - r.left - 250);
      yTo(e.clientY - r.top - 250);
    };
    parent.addEventListener('mousemove', move);
    return () => parent.removeEventListener('mousemove', move);
  }, [ok]);
  if (!ok) return null;
  return (
    <div
      ref={ref}
      className={`pointer-events-none absolute left-0 top-0 h-[500px] w-[500px] rounded-full bg-[radial-gradient(circle,rgba(108,71,255,0.35),transparent_65%)] blur-2xl ${className}`}
    />
  );
}
