'use client';

import { useCallback, useEffect, useMemo, useRef, useState, FormEvent, DragEvent } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Globe,
  Layers,
  Link2,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import { AxiosError } from 'axios';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Button, Card, EmptyState, ErrorBanner, SkeletonCard } from '@/components/ui';
import { CountUp } from '@/components/motion';
import { useAuth } from '@/context/AuthContext';
import {
  createDocument,
  createKnowledgeSource,
  deleteDocument,
  embedDocument,
  ingestUrl,
  listDocumentChunks,
  listDocuments,
  listKnowledgeSources,
  reindexKnowledge,
  searchKnowledge,
  uploadDocument,
} from '@/api/knowledge';
import type { DocumentChunk, KnowledgeDocument, KnowledgeSearchResult, KnowledgeSource } from '@/types';

const ACCEPT = '.pdf,.docx,.txt,.md';
const MAX_MB = 10;

function errMsg(e: unknown): string {
  if (e instanceof AxiosError) {
    const d = e.response?.data?.detail;
    return typeof d === 'string' ? d : e.message;
  }
  return 'Something went wrong';
}

function fileKind(d: KnowledgeDocument): string {
  const ext = (d.filename ?? '').split('.').pop()?.toLowerCase();
  if (d.metadata_json && 'source_url' in d.metadata_json) return 'url';
  return ext && ext.length <= 5 ? ext : 'txt';
}

function StatusChip({ doc }: { doc: KnowledgeDocument }) {
  if (doc.status === 'completed')
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
        <CheckCircle2 className="h-3 w-3" /> Ready
      </span>
    );
  if (doc.status === 'failed')
    return (
      <span
        title={doc.error_message ?? ''}
        className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-medium text-red-700 ring-1 ring-inset ring-red-200"
      >
        <AlertTriangle className="h-3 w-3" /> Failed
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
      <Loader2 className="h-3 w-3 animate-spin" /> Embedding
    </span>
  );
}

function Bar({ label, value }: { label: string; value: number | null }) {
  const v = value == null ? 0 : Math.max(0, Math.min(1, value));
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 font-mono text-[10px] uppercase tracking-wider text-slate-400">{label}</span>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-fg/10">
        <motion.span
          initial={{ width: 0 }}
          animate={{ width: `${v * 100}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="block h-full rounded-full bg-gradient-to-r from-iris to-aqua"
        />
      </span>
      <span className="w-9 text-right font-mono text-[10px] text-slate-500">{value == null ? '—' : value.toFixed(2)}</span>
    </div>
  );
}

export default function KnowledgePage() {
  const { role } = useAuth();
  const canManage = role === 'OWNER' || role === 'ADMIN';

  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'documents' | 'test'>('documents');

  // upload
  const [mode, setMode] = useState<'file' | 'text' | 'url'>('file');
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const [textTitle, setTextTitle] = useState('');
  const [textBody, setTextBody] = useState('');
  const [url, setUrl] = useState('');
  const [busyForm, setBusyForm] = useState(false);

  // chunk viewer
  const [viewing, setViewing] = useState<KnowledgeDocument | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);

  // retrieval playground
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<KnowledgeSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const [srcs, docs] = await Promise.all([listKnowledgeSources(), listDocuments()]);
      setSources(srcs);
      setDocuments(docs);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while anything is still embedding so status flips to Ready without a reload.
  const anyProcessing = useMemo(() => documents.some((d) => d.status === 'processing' || d.status === 'pending'), [documents]);
  useEffect(() => {
    if (!anyProcessing) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [anyProcessing, refresh]);

  const totalChunks = documents.reduce((n, d) => n + d.chunk_count, 0);

  // A source is just a container; create one on first use so uploading never requires setup.
  const ensureSource = async (): Promise<string> => {
    if (sources.length > 0) return sources[0].id;
    const s = await createKnowledgeSource({ name: 'Help Center', source_type: 'txt' });
    setSources([s]);
    return s.id;
  };

  const handleFiles = async (files: FileList | File[]) => {
    if (!canManage) return;
    setError('');
    setNotice('');
    const list = Array.from(files);
    const bad = list.filter((f) => !ACCEPT.split(',').some((ext) => f.name.toLowerCase().endsWith(ext)));
    if (bad.length) {
      setError(`Unsupported file type: ${bad.map((b) => b.name).join(', ')}. Use PDF, DOCX, TXT or MD.`);
      return;
    }
    const big = list.filter((f) => f.size > MAX_MB * 1024 * 1024);
    if (big.length) {
      setError(`${big.map((b) => b.name).join(', ')} exceeds the ${MAX_MB} MB limit.`);
      return;
    }
    try {
      const sourceId = await ensureSource();
      for (const f of list) {
        setUploading((u) => [...u, f.name]);
        try {
          await uploadDocument(f, sourceId);
        } catch (e) {
          setError(`${f.name}: ${errMsg(e)}`);
        } finally {
          setUploading((u) => u.filter((n) => n !== f.name));
        }
      }
      await refresh();
      setNotice('Uploaded. Documents are being chunked and embedded; they become searchable when marked Ready.');
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files);
  };

  const submitText = async (e: FormEvent) => {
    e.preventDefault();
    setBusyForm(true);
    setError('');
    try {
      await createDocument({ knowledge_source_id: await ensureSource(), title: textTitle, content: textBody });
      setTextTitle('');
      setTextBody('');
      await refresh();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusyForm(false);
    }
  };

  const submitUrl = async (e: FormEvent) => {
    e.preventDefault();
    setBusyForm(true);
    setError('');
    try {
      await ingestUrl(await ensureSource(), url);
      setUrl('');
      await refresh();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusyForm(false);
    }
  };

  const openChunks = async (doc: KnowledgeDocument) => {
    setViewing(doc);
    setChunks([]);
    setChunksLoading(true);
    try {
      setChunks(await listDocumentChunks(doc.id));
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setChunksLoading(false);
    }
  };

  const remove = async (doc: KnowledgeDocument) => {
    if (!confirm(`Delete “${doc.title}”? The AI will stop using it immediately.`)) return;
    try {
      await deleteDocument(doc.id);
      setDocuments((d) => d.filter((x) => x.id !== doc.id));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const retry = async (doc: KnowledgeDocument) => {
    try {
      await embedDocument(doc.id);
    } catch (e) {
      setError(errMsg(e));
    }
    refresh();
  };

  const reindexAll = async () => {
    if (!confirm('Re-chunk and re-embed every document? Use this after changing the embedding model.')) return;
    try {
      const r = await reindexKnowledge();
      setNotice(`Re-indexing ${r.documents} document(s)…`);
      refresh();
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const runSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError('');
    try {
      setResults((await searchKnowledge({ query, top_k: 5 })).results);
    } catch (err) {
      setSearchError(errMsg(err));
    } finally {
      setSearching(false);
    }
  };

  return (
    <ProtectedRoute>
      <AppLayout title="Knowledge Base">
        <div className="mb-6 mt-2 flex flex-wrap items-end justify-between gap-4">
          <p className="max-w-xl text-slate-500">
            Upload your documents. The assistant answers <em className="text-slate-700">only</em> from what is here, with citations, and hands off to a
            person when the documents don&apos;t cover a question.
          </p>
          <div className="flex gap-6">
            <div>
              <p className="font-display text-5xl leading-none text-slate-950"><CountUp value={documents.length} duration={0.8} /></p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">documents</p>
            </div>
            <div>
              <p className="font-display text-5xl leading-none text-slate-950"><CountUp value={totalChunks} duration={0.8} /></p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">passages</p>
            </div>
          </div>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
        {notice && (
          <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{notice}</div>
        )}

        {/* Tabs */}
        <div className="glass mb-5 inline-flex rounded-full p-1">
          {(['documents', 'test'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`relative rounded-full px-5 py-2 text-[13px] font-medium transition-colors ${tab === t ? 'text-bg' : 'text-slate-500 hover:text-slate-900'}`}
            >
              {tab === t && <motion.span layoutId="kb-tab" className="absolute inset-0 rounded-full bg-fg" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
              <span className="relative">{t === 'documents' ? 'Documents' : 'Test retrieval'}</span>
            </button>
          ))}
        </div>

        {tab === 'documents' && (
          <>
            {canManage && (
              <Card className="mb-6 p-5">
                <div className="mb-4 flex gap-1.5">
                  {([['file', UploadCloud, 'Upload files'], ['text', FileText, 'Paste text'], ['url', Globe, 'Web page']] as const).map(([m, Icon, label]) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
                        mode === m ? 'bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-200' : 'text-slate-500 hover:text-slate-900'
                      }`}
                    >
                      <Icon className="h-3.5 w-3.5" /> {label}
                    </button>
                  ))}
                </div>

                {mode === 'file' && (
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={onDrop}
                    onClick={() => fileRef.current?.click()}
                    className={`group cursor-pointer rounded-3xl border-2 border-dashed px-6 py-12 text-center transition-all ${
                      dragging ? 'scale-[1.01] border-iris bg-iris/10' : 'border-line-strong hover:border-iris/60 hover:bg-fg/[0.03]'
                    }`}
                  >
                    <input ref={fileRef} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => e.target.files && handleFiles(e.target.files)} />
                    <motion.div animate={dragging ? { y: -6 } : { y: 0 }} className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-iris/15 text-iris">
                      <UploadCloud className="h-6 w-6" />
                    </motion.div>
                    <p className="font-display text-2xl text-slate-950">Drop documents here</p>
                    <p className="mt-1 text-sm text-slate-500">
                      or <span className="text-indigo-600">browse</span>. PDF, DOCX, TXT, MD up to {MAX_MB} MB each
                    </p>
                    {uploading.length > 0 && (
                      <div className="mt-4 flex flex-wrap justify-center gap-2">
                        {uploading.map((n) => (
                          <span key={n} className="inline-flex items-center gap-1.5 rounded-full bg-fg/5 px-3 py-1 text-xs text-slate-600">
                            <Loader2 className="h-3 w-3 animate-spin" /> {n}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {mode === 'text' && (
                  <form onSubmit={submitText} className="space-y-3">
                    <input required value={textTitle} onChange={(e) => setTextTitle(e.target.value)} placeholder="Title, e.g. Returns policy" className="w-full rounded-2xl border border-line bg-fg/[0.04] px-4 py-2.5 text-sm outline-none focus:border-iris focus:ring-4 focus:ring-iris/20" />
                    <textarea required rows={6} value={textBody} onChange={(e) => setTextBody(e.target.value)} placeholder="Paste the document text…" className="w-full rounded-2xl border border-line bg-fg/[0.04] px-4 py-2.5 text-sm outline-none focus:border-iris focus:ring-4 focus:ring-iris/20" />
                    <Button type="submit" loading={busyForm}>Add document</Button>
                  </form>
                )}

                {mode === 'url' && (
                  <form onSubmit={submitUrl} className="flex gap-2">
                    <div className="flex flex-1 items-center gap-2 rounded-full border border-line bg-fg/[0.04] px-4">
                      <Link2 className="h-4 w-4 text-slate-400" />
                      <input required type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/help/returns" className="w-full bg-transparent py-2.5 text-sm outline-none" />
                    </div>
                    <Button type="submit" loading={busyForm}>Import page</Button>
                  </form>
                )}
              </Card>
            )}

            {loading ? (
              <div className="grid gap-4 md:grid-cols-2"><SkeletonCard /><SkeletonCard /></div>
            ) : documents.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<Layers className="h-5 w-5" />}
                  title="No documents yet"
                  description="Upload a PDF, Word file or text and the assistant can start answering from it."
                />
              </Card>
            ) : (
              <div className="grid gap-3">
                <AnimatePresence initial={false}>
                  {documents.map((d) => (
                    <motion.div
                      key={d.id}
                      layout
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.97 }}
                      className="glass group flex flex-wrap items-center gap-4 rounded-3xl p-4 pr-5 transition-colors hover:border-line-strong"
                    >
                      <span className="grid h-12 w-12 flex-shrink-0 place-items-center rounded-2xl bg-fg/[0.06] font-mono text-[11px] font-semibold uppercase text-iris">
                        {fileKind(d)}
                      </span>
                      <button onClick={() => openChunks(d)} className="min-w-0 flex-1 text-left">
                        <p className="truncate text-[15px] font-medium text-slate-950 group-hover:text-indigo-600">{d.title}</p>
                        <p className="mt-0.5 text-xs text-slate-400">
                          {d.chunk_count} passage{d.chunk_count === 1 ? '' : 's'} · added {new Date(d.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </p>
                        {d.status === 'failed' && d.error_message && (
                          <p className="mt-1 line-clamp-2 text-xs text-red-600">{d.error_message}</p>
                        )}
                      </button>
                      <StatusChip doc={d} />
                      {canManage && (
                        <div className="flex items-center gap-1">
                          {d.status === 'failed' && (
                            <button onClick={() => retry(d)} title="Retry embedding" className="grid h-9 w-9 place-items-center rounded-full text-slate-500 transition-colors hover:bg-fg/10 hover:text-slate-950">
                              <RefreshCw className="h-4 w-4" />
                            </button>
                          )}
                          <button onClick={() => remove(d)} title="Delete" className="grid h-9 w-9 place-items-center rounded-full text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
                {canManage && (
                  <button onClick={reindexAll} className="mx-auto mt-2 inline-flex items-center gap-1.5 text-xs text-slate-400 transition-colors hover:text-slate-700">
                    <RefreshCw className="h-3.5 w-3.5" /> Re-index all documents
                  </button>
                )}
              </div>
            )}
          </>
        )}

        {tab === 'test' && (
          <div>
            <p className="mb-4 max-w-xl text-sm text-slate-500">
              Ask a question to see exactly which passages the assistant would be given. Passages that aren&apos;t relevant enough are never shown to it.
            </p>
            <form onSubmit={runSearch} className="glass mb-6 flex items-center gap-2 rounded-full py-1.5 pl-5 pr-1.5">
              <Search className="h-4 w-4 text-slate-400" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. how long do I have to return something?" className="flex-1 bg-transparent py-2 text-sm outline-none" />
              <Button type="submit" loading={searching}>Search</Button>
            </form>
            {searchError && <div className="mb-4"><ErrorBanner message={searchError} /></div>}

            {results && results.length === 0 && (
              <Card>
                <EmptyState
                  icon={<AlertTriangle className="h-5 w-5" />}
                  title="Nothing relevant found"
                  description="The assistant would not answer this from the documents. It would say so and offer a human instead of guessing."
                />
              </Card>
            )}
            <div className="grid gap-3">
              {results?.map((r, i) => (
                <motion.div key={r.chunk_id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }} className="glass rounded-3xl p-5">
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                    <span className="grid h-6 w-6 place-items-center rounded-full bg-iris/15 font-mono text-[11px] font-bold text-iris">{i + 1}</span>
                    <span className="font-medium text-slate-900">{r.document_title}</span>
                    {r.section && <span className="rounded-full bg-fg/5 px-2 py-0.5 text-slate-500">{r.section}</span>}
                    {r.page && <span className="rounded-full bg-fg/5 px-2 py-0.5 text-slate-500">page {r.page}</span>}
                    <span className="ml-auto font-mono text-[11px] text-aqua">relevance {r.similarity_score.toFixed(2)}</span>
                  </div>
                  <p className="text-sm leading-relaxed text-slate-700">{r.content}</p>
                  <div className="mt-3 grid gap-1.5 sm:grid-cols-3">
                    <Bar label="meaning" value={r.dense_score} />
                    <Bar label="keywords" value={r.keyword_score} />
                    <Bar label="coverage" value={r.coverage} />
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* Chunk viewer drawer */}
        <AnimatePresence>
          {viewing && (
            <motion.div key="drawer" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setViewing(null)} className="fixed inset-0 z-50 flex justify-end bg-black/55 backdrop-blur-sm">
              <motion.aside
                initial={{ x: 480 }}
                animate={{ x: 0 }}
                exit={{ x: 480 }}
                transition={{ type: 'spring', stiffness: 320, damping: 34 }}
                onClick={(e) => e.stopPropagation()}
                className="flex h-full w-full max-w-lg flex-col border-l border-line bg-surface"
              >
                <div className="flex items-start justify-between gap-3 border-b border-line p-6">
                  <div className="min-w-0">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-400">Passages the AI can use</p>
                    <h3 className="mt-1 truncate font-display text-3xl text-slate-950">{viewing.title}</h3>
                  </div>
                  <button onClick={() => setViewing(null)} className="grid h-9 w-9 place-items-center rounded-full text-slate-400 hover:bg-fg/10 hover:text-slate-950">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <div className="flex-1 space-y-3 overflow-y-auto p-6">
                  {chunksLoading && <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>}
                  {chunks.map((c) => {
                    const meta = (c.metadata_json ?? {}) as { section?: string; page?: number };
                    return (
                      <div key={c.id} className="rounded-2xl border border-line bg-fg/[0.03] p-4">
                        <div className="mb-2 flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-slate-400">
                          <span>#{c.chunk_index + 1}</span>
                          {meta.section && <span className="rounded-full bg-fg/5 px-2 py-0.5 normal-case tracking-normal text-slate-500">{meta.section}</span>}
                          {meta.page && <span>p.{meta.page}</span>}
                          <span className={`ml-auto ${c.has_embedding ? 'text-aqua' : 'text-amber-600'}`}>{c.has_embedding ? `vector · ${c.embedding_model ?? ''}` : 'no vector'}</span>
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{c.content}</p>
                      </div>
                    );
                  })}
                </div>
              </motion.aside>
            </motion.div>
          )}
        </AnimatePresence>
      </AppLayout>
    </ProtectedRoute>
  );
}
