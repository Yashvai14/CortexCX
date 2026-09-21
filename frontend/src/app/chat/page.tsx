'use client';

import { useState, FormEvent, useRef, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '@/context/AuthContext';

interface ChatMsg {
  sender: 'customer' | 'ai';
  text: string;
  time: string;
  sources?: Array<{ document_title: string; score: number }>;
  escalated?: boolean;
}

export default function StorefrontChatPage() {
  const { workspace } = useAuth();
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      sender: 'ai',
      text: 'Hello! Welcome to our store. How can I help you today? You can ask about our products, track an order, or check our shipping and return policies.',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => 'sess_' + Math.random().toString(36).substring(2, 9));
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading || !workspace) return;

    const userText = input.trim();
    setInput('');

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages((prev) => [...prev, { sender: 'customer', text: userText, time: now }]);
    setLoading(true);

    try {
      const resp = await axios.post('http://127.0.0.1:8000/channels/webchat/message', {
        workspace_id: workspace.id,
        session_id: sessionId,
        content: userText,
        customer_name: 'Store Visitor',
      });

      const reply = resp.data;
      setMessages((prev) => [
        ...prev,
        {
          sender: 'ai',
          text: reply.content,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sources: reply.sources,
          escalated: reply.escalated,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'ai',
          text: 'Sorry, I encountered an issue connecting to support. Please try again.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[640px]">
        {/* Header */}
        <div className="bg-indigo-600 px-6 py-4 flex items-center justify-between text-white">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center font-bold text-sm">
              ✦
            </div>
            <div>
              <h3 className="font-semibold text-sm">Storefront Support Assistant</h3>
              <p className="text-xs text-indigo-200">Powered by CortexCX AI Engine</p>
            </div>
          </div>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-100 border border-emerald-400/30">
            ● Online
          </span>
        </div>

        {/* Message area */}
        <div className="flex-1 p-5 overflow-y-auto space-y-3.5 bg-slate-50/50">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${m.sender === 'customer' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                  m.sender === 'customer'
                    ? 'bg-indigo-600 text-white rounded-br-none'
                    : m.escalated
                    ? 'bg-amber-50 text-amber-900 border border-amber-200 rounded-bl-none'
                    : 'bg-white text-slate-800 border border-slate-200 rounded-bl-none'
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
                    <span className="font-semibold">Sources: </span>
                    {m.sources.map((s, sIdx) => (
                      <span key={sIdx} className="bg-slate-100 px-1.5 py-0.5 rounded mr-1">
                        {s.document_title}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-400 mt-1 px-1">{m.time}</span>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-1.5 text-xs text-slate-400 pl-2">
              <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" />
              <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce [animation-delay:0.2s]" />
              <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce [animation-delay:0.4s]" />
              <span className="ml-1">CortexCX AI is replying...</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <form onSubmit={handleSend} className="p-3 bg-white border-t border-slate-200 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your question (e.g. 'Track order #ORD-1001')..."
            className="flex-1 px-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
