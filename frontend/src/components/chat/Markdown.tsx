'use client';

import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Renders assistant Markdown (paragraphs, **bold**, lists, numbered steps, tables, headings).
 *
 * react-markdown never injects raw HTML (it is skipped, not rendered), so model output cannot add scripts or
 * markup; links are forced to open safely in a new tab.
 */
const components: Components = {
  p: ({ children }) => <p className="leading-[1.65] [&:not(:last-child)]:mb-3">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-fg">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1.5 pl-5 marker:text-iris last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1.5 pl-5 marker:font-medium marker:text-iris last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-[1.6]">{children}</li>,
  h1: ({ children }) => <h4 className="mb-1.5 mt-3 text-[15px] font-semibold text-fg first:mt-0">{children}</h4>,
  h2: ({ children }) => <h4 className="mb-1.5 mt-3 text-[15px] font-semibold text-fg first:mt-0">{children}</h4>,
  h3: ({ children }) => <h4 className="mb-1.5 mt-3 text-sm font-semibold uppercase tracking-wide text-slate-500 first:mt-0">{children}</h4>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-indigo-600 underline underline-offset-2">
      {children}
    </a>
  ),
  blockquote: ({ children }) => <blockquote className="mb-3 border-l-2 border-iris/50 pl-3 text-slate-600">{children}</blockquote>,
  code: ({ children }) => <code className="rounded bg-fg/10 px-1 py-0.5 font-mono text-[13px]">{children}</code>,
  hr: () => <hr className="my-3 border-line" />,
  table: ({ children }) => (
    <div className="mb-3 overflow-x-auto rounded-2xl border border-line last:mb-0">
      <table className="w-full border-collapse text-left text-[13.5px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-fg/[0.06] text-slate-600">{children}</thead>,
  th: ({ children }) => <th className="px-3.5 py-2 font-medium">{children}</th>,
  td: ({ children }) => <td className="border-t border-line px-3.5 py-2 align-top">{children}</td>,
};

export function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml>
      {text}
    </ReactMarkdown>
  );
}
