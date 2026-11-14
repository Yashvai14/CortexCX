'use client';

import { useState, FormEvent, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import Link from 'next/link';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowUp, ArrowLeft, RotateCw, SearchX, Sparkles } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Logo } from '@/components/layout/Logo';
import { CursorGlow } from '@/components/motion';
import { Markdown } from '@/components/chat/Markdown';
import { Sources, type ChatSource } from '@/components/chat/Sources';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

interface ChatMsg {
  sender: 'customer' | 'ai';
  text: string;
  time: string;
  sources?: ChatSource[];
  suggestions?: string[];
  escalated?: boolean;
  /** The answer could not be produced; offers a retry that reuses the same message id (no duplicate sent). */
  failed?: { prompt: string; clientId: string };
}

type Phase = 'thinking' | 'searching' | 'writing';
const PHASE_TEXT: Record<Phase, string> = {
  thinking: 'Thinking…',
  searching: 'Searching our policies…',
  writing: 'Writing your answer…',
};

interface Reply {
  content: string;
  sources?: ChatSource[];
  suggestions?: string[];
  escalated?: boolean;
}

/** POST a message and read the Server-Sent Events stream: real stage updates, then the validated answer. */
async function askStreaming(
  body: Record<string, unknown>,
  onPhase: (p: Phase) => void,
): Promise<Reply> {
  const res = await fetch(`${API}/channels/webchat/message/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let final: Reply | null = null;

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const event = /^event: (.+)$/m.exec(raw)?.[1];
      const data = /^data: (.+)$/m.exec(raw)?.[1];
      if (!event || !data) continue;
      const parsed = JSON.parse(data);
      if (event === 'stage') onPhase(parsed.stage as Phase);
      else if (event === 'final') final = parsed as Reply;
      else if (event === 'error') throw new Error(parsed.message || 'error');
    }
  }
  if (!final) throw new Error('stream ended without an answer');
  return final;
}

const starterSuggestions = ['What is your return policy?', 'How long does a refund take?', 'Track order #ORD-1001'];
const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const newId = () => 'm_' + Math.random().toString(36).slice(2, 12);

export default function StorefrontChatPage() {
  const { workspace, isLoading: authLoading } = useAuth();
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      sender: 'ai',
      text: 'Hello! Welcome to our store. How can I help you today? You can ask about our products, track an order, or check our shipping, return and refund policies.',
      time: '',
    },
  ]);
  const [input, setInput] = useState('');
  const [phase, setPhase] = useState<Phase | null>(null);
  const [sessionId] = useState(() => 'sess_' + Math.random().toString(36).substring(2, 9));
  const [awaitingConfirm, setAwaitingConfirm] = useState(false);
  const seenIds = useRef<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);
  const loading = phase !== null;

  // While a human is involved, pull in their replies and the "is it resolved?" question.
  useEffect(() => {
    if (!workspace) return;
    const timer = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/channels/webchat/history/${sessionId}`, {
          params: { workspace_id: workspace.id },
        });
        setAwaitingConfirm(data.ai_state === 'awaiting_confirmation');
        const fresh = (data.messages || []).filter(
          (m: { id: string; sender_type: string }) =>
            (m.sender_type === 'agent' || m.sender_type === 'system') && !seenIds.current.has(m.id),
        );
        if (fresh.length) {
          fresh.forEach((m: { id: string }) => seenIds.current.add(m.id));
          setMessages((prev) => [
            ...prev,
            ...fresh.map((m: { content: string; sender_type: string }) => ({
              sender: 'ai' as const,
              text: m.sender_type === 'agent' ? `Support agent: ${m.content}` : m.content,
              time: now(),
            })),
          ]);
        }
      } catch {
        /* ignore transient polling errors */
      }
    }, 4000);
    return () => clearInterval(timer);
  }, [workspace, sessionId]);

  useEffect(() => {
    setMessages((p) => p.map((m, i) => (i === 0 && !m.time ? { ...m, time: now() } : m)));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, phase]);

  const ask = useCallback(
    async (text: string, clientId: string) => {
      if (!workspace) return;
      setPhase('thinking');
      try {
        const reply = await askStreaming(
          {
            workspace_id: workspace.id,
            session_id: sessionId,
            content: text,
            customer_name: 'Store Visitor',
            client_message_id: clientId, // makes a retry safe: the server will not store the message twice
          },
          setPhase,
        );
        setMessages((prev) => [
          ...prev.filter((m) => m.failed?.clientId !== clientId),
          {
            sender: 'ai',
            text: reply.content,
            time: now(),
            sources: reply.sources,
            suggestions: reply.suggestions,
            escalated: reply.escalated,
          },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev.filter((m) => m.failed?.clientId !== clientId),
          {
            sender: 'ai',
            text: "Sorry, I couldn't prepare an answer just now. Please try again.",
            time: now(),
            failed: { prompt: text, clientId },
          },
        ]);
      } finally {
        setPhase(null);
      }
    },
    [workspace, sessionId],
  );

  const send = (text: string) => {
    if (!text.trim() || loading || !workspace) return;
    setInput('');
    setAwaitingConfirm(false);
    setMessages((prev) => [...prev, { sender: 'customer', text, time: now() }]);
    ask(text, newId());
  };

  const retry = (failed: NonNullable<ChatMsg['failed']>) => {
    if (loading) return;
    ask(failed.prompt, failed.clientId); // same id: no second copy of the customer's message
  };

  const handleSend = (e: FormEvent) => {
    e.preventDefault();
    send(input.trim());
  };

  const lastAi = [...messages].reverse().find((m) => m.sender === 'ai');

  return (
    <div data-theme="dark" className="relative flex min-h-screen items-center justify-center overflow-hidden bg-bg p-4 text-slate-900">
      <div className="aurora" aria-hidden><i /></div>
      <div className="absolute inset-0 bg-grid [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
      <div className="absolute -left-20 top-0 h-[420px] w-[420px] rounded-full bg-indigo-600/40 blur-[120px]" />
      <div className="absolute -right-20 bottom-0 h-[420px] w-[420px] rounded-full bg-mint/20 blur-[120px]" />
      <CursorGlow />

      <Link
        href="/dashboard"
        className="absolute left-5 top-5 z-10 flex items-center gap-1.5 rounded-full glass-dark px-4 py-2 text-sm text-slate-300 transition-colors hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" /> Dashboard
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 40, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 120, damping: 18 }}
        className="edge-glow relative flex h-[min(820px,95vh)] w-full max-w-2xl flex-col overflow-hidden rounded-[32px] border border-line bg-surface/80 shadow-[0_50px_100px_-30px_rgba(139,123,255,0.45)] backdrop-blur-2xl"
      >
        {/* Header */}
        <div className="relative flex items-center justify-between overflow-hidden border-b border-line px-6 py-5 text-white">
          <div className="absolute -right-10 -top-16 h-40 w-40 rounded-full bg-indigo-600/60 blur-3xl" />
          <div className="relative flex items-center gap-3">
            <Logo size={40} dark />
            <div className="leading-tight">
              <h3 className="font-display text-xl">Storefront Assistant</h3>
              <p className="text-xs text-slate-400">Answers from our policies, with sources</p>
            </div>
          </div>
          <span className="relative flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-mint">
            <span className="relative flex h-2 w-2">
              <span className="absolute h-full w-full rounded-full bg-mint animate-pulse-ring" />
              <span className="relative h-2 w-2 rounded-full bg-mint" />
            </span>
            Online
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 space-y-4 overflow-y-auto bg-[radial-gradient(circle_at_top,rgb(139_123_255/0.12),transparent_60%)] p-5">
          <AnimatePresence initial={false}>
            {messages.map((m, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 16, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: 'spring', stiffness: 380, damping: 28 }}
                className={`flex flex-col ${m.sender === 'customer' ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`max-w-[94%] px-5 py-3.5 text-[14.5px] ${
                    m.sender === 'customer'
                      ? 'rounded-3xl rounded-br-lg bg-gradient-to-br from-iris to-indigo-600 text-white'
                      : m.failed
                      ? 'rounded-3xl rounded-bl-lg border border-red-200 bg-red-50 text-red-700'
                      : m.escalated
                      ? 'rounded-3xl rounded-bl-lg border border-amber-200 bg-amber-50 text-amber-800'
                      : 'rounded-3xl rounded-bl-lg border border-line bg-fg/[0.05] text-slate-800'
                  }`}
                >
                  {m.sender === 'customer' ? (
                    <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
                  ) : (
                    <>
                      {m.escalated && (
                        <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide opacity-80">
                          <SearchX className="h-3.5 w-3.5" /> Passed to our team
                        </p>
                      )}
                      <Markdown text={m.text} />
                      {m.failed && (
                        <button
                          onClick={() => retry(m.failed!)}
                          disabled={loading}
                          className="mt-2.5 inline-flex items-center gap-1.5 rounded-full border border-red-300 bg-white/10 px-3.5 py-1.5 text-xs font-medium transition-colors hover:bg-white/20 disabled:opacity-50"
                        >
                          <RotateCw className="h-3.5 w-3.5" /> Try again
                        </button>
                      )}
                      {m.sources && m.sources.length > 0 && <Sources sources={m.sources} />}
                    </>
                  )}
                </div>
                <span className="mt-1 px-2 text-[10px] text-slate-400">{m.time}</span>
              </motion.div>
            ))}

            {loading && (
              <motion.div
                key="status"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex w-fit items-center gap-2.5 rounded-3xl rounded-bl-lg border border-line bg-fg/[0.05] px-4 py-3"
                aria-live="polite"
              >
                <span className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="h-1.5 w-1.5 rounded-full bg-indigo-500"
                      animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
                      transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }}
                    />
                  ))}
                </span>
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span
                    key={phase}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="text-xs text-slate-500"
                  >
                    {PHASE_TEXT[phase!]}
                  </motion.span>
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Grounded follow-ups from the latest answer */}
          {!loading && lastAi?.suggestions && lastAi.suggestions.length > 0 && messages[messages.length - 1] === lastAi && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap items-center gap-2 pl-1">
              <Sparkles className="h-3.5 w-3.5 text-iris" />
              {lastAi.suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-iris/40 bg-iris/10 px-3 py-1.5 text-xs text-indigo-700 transition-colors hover:bg-iris/25"
                >
                  {s}
                </button>
              ))}
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Quick replies + input */}
        <div className="border-t border-line bg-transparent p-4">
          {awaitingConfirm && (
            <div className="mb-3 flex flex-wrap gap-2">
              {["Yes, it's resolved", 'No, I still need help'].map((s) => (
                <motion.button
                  key={s}
                  whileHover={{ y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => send(s)}
                  className="rounded-full border border-iris/50 bg-iris/10 px-4 py-2 text-xs font-medium text-fg transition-colors hover:bg-iris/25"
                >
                  {s}
                </motion.button>
              ))}
            </div>
          )}
          {!awaitingConfirm && messages.length < 3 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {starterSuggestions.map((s) => (
                <motion.button
                  key={s}
                  whileHover={{ y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => send(s)}
                  className="rounded-full border border-line bg-fg/[0.04] px-3 py-1.5 text-xs text-slate-600 transition-colors hover:border-iris/50 hover:bg-iris/10 hover:text-indigo-700"
                >
                  {s}
                </motion.button>
              ))}
            </div>
          )}
          {!authLoading && !workspace && (
            <div className="mb-3 rounded-2xl border border-amber-300/40 bg-amber-400/10 px-4 py-2.5 text-xs text-amber-200">
              You are not signed in on this address, so messages cannot be sent.{' '}
              <Link href="/login" className="font-semibold underline">Sign in</Link> and come back to this page.
            </div>
          )}
          <form onSubmit={handleSend} className="flex items-center gap-2 rounded-full border border-line bg-fg/[0.04] py-1.5 pl-5 pr-1.5 transition focus-within:border-iris focus-within:bg-fg/[0.07] focus-within:ring-4 focus-within:ring-iris/20">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about returns, refunds, orders…"
              className="flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
            />
            <motion.button
              type="submit"
              disabled={loading || !input.trim()}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.88 }}
              aria-label="Send"
              className="grid h-10 w-10 place-items-center rounded-full bg-snow text-ink transition-colors hover:bg-iris disabled:opacity-30"
            >
              <ArrowUp className="h-4 w-4" />
            </motion.button>
          </form>
        </div>
      </motion.div>
    </div>
  );
}
