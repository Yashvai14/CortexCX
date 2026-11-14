'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronDown, FileText } from 'lucide-react';

export interface ChatSource {
  source_id?: string;
  document_title: string;
  document_name?: string;
  page?: number | null;
  page_end?: number | null;
  section?: string | null;
  section_number?: string | null;
  excerpt?: string;
  score?: number;
}

const cleanName = (t: string) => t.replace(/\.(pdf|docx?|txt|md)$/i, '').replace(/[_-]+/g, ' ');

function pageLabel(s: ChatSource): string | null {
  if (!s.page) return null;
  return s.page_end && s.page_end !== s.page ? `Pages ${s.page}–${s.page_end}` : `Page ${s.page}`;
}

/**
 * Compact "Sources" block. Collapsed it is one line; open it lists only the passages the answer actually used, each
 * with document, page and section, and expands to the supporting excerpt.
 */
export function Sources({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<string | null>(null);
  if (!sources.length) return null;

  return (
    <div className="mt-3.5 border-t border-line pt-2.5">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 text-xs text-slate-500 transition-colors hover:text-slate-900"
      >
        <FileText className="h-3.5 w-3.5 text-iris" />
        <span className="font-medium">
          Sources <span className="text-slate-400">· {sources.length}</span>
        </span>
        {!open && (
          <span className="min-w-0 flex-1 truncate text-left text-slate-400">
            {sources.map((s) => s.section).filter(Boolean).join(' · ')}
          </span>
        )}
        <ChevronDown className={`ml-auto h-3.5 w-3.5 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="mt-2 space-y-1.5 overflow-hidden"
          >
            {sources.map((s, i) => {
              const id = s.source_id ?? String(i);
              const isActive = active === id;
              const meta = [pageLabel(s), s.section_number ? `§ ${s.section_number}` : null].filter(Boolean).join(' · ');
              return (
                <li key={id} className="rounded-2xl border border-line bg-fg/[0.03]">
                  <button
                    onClick={() => s.excerpt && setActive(isActive ? null : id)}
                    className={`flex w-full items-start gap-2.5 px-3 py-2 text-left ${s.excerpt ? 'cursor-pointer' : 'cursor-default'}`}
                  >
                    <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12.5px] font-medium text-slate-800">{s.section ?? cleanName(s.document_title)}</span>
                      <span className="block truncate text-[11px] text-slate-400">
                        {cleanName(s.document_name ?? s.document_title)}
                        {meta ? ` · ${meta}` : ''}
                      </span>
                    </span>
                    {s.excerpt && <ChevronDown className={`mt-1 h-3 w-3 shrink-0 text-slate-400 transition-transform ${isActive ? 'rotate-180' : ''}`} />}
                  </button>
                  <AnimatePresence initial={false}>
                    {isActive && s.excerpt && (
                      <motion.p
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden px-3 pb-2.5 pl-[2.1rem] text-[12px] italic leading-relaxed text-slate-500"
                      >
                        “{s.excerpt}”
                      </motion.p>
                    )}
                  </AnimatePresence>
                </li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
