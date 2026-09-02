'use client';

import { useEffect, useState, FormEvent } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import {
  Button, Card, SkeletonCard, EmptyState, ErrorBanner, DocumentStatusBadge, Badge,
} from '@/components/ui';
import {
  listKnowledgeSources, listDocuments, embedDocument,
  searchKnowledge, createKnowledgeSource, createDocument,
} from '@/api/knowledge';
import type { KnowledgeSource, KnowledgeDocument, KnowledgeSearchResult } from '@/types';
import { AxiosError } from 'axios';
import { useAuth } from '@/context/AuthContext';

export default function KnowledgePage() {
  const { role } = useAuth();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'documents' | 'search'>('documents');

  // Search state
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');

  // Create document state
  const [showCreateDoc, setShowCreateDoc] = useState(false);
  const [docTitle, setDocTitle] = useState('');
  const [docContent, setDocContent] = useState('');
  const [docSourceId, setDocSourceId] = useState('');
  const [creating, setCreating] = useState(false);

  // Embedding state
  const [embeddingId, setEmbeddingId] = useState<string | null>(null);

  const canManage = role === 'OWNER' || role === 'ADMIN';

  useEffect(() => {
    const load = async () => {
      try {
        const [srcs, docs] = await Promise.all([listKnowledgeSources(), listDocuments()]);
        setSources(srcs);
        setDocuments(docs);
        if (srcs.length > 0 && !docSourceId) setDocSourceId(srcs[0].id);
      } catch (err) {
        if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError('');
    setSearchResults([]);
    try {
      const resp = await searchKnowledge({ query, top_k: 5 });
      setSearchResults(resp.results);
    } catch (err) {
      if (err instanceof AxiosError) setSearchError(err.response?.data?.detail ?? err.message);
    } finally {
      setSearching(false);
    }
  };

  const handleCreateDoc = async (e: FormEvent) => {
    e.preventDefault();
    if (!docSourceId) return;
    setCreating(true);
    try {
      const doc = await createDocument({
        knowledge_source_id: docSourceId,
        title: docTitle,
        content: docContent,
      });
      setDocuments((prev) => [doc, ...prev]);
      setDocTitle('');
      setDocContent('');
      setShowCreateDoc(false);
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleEmbed = async (docId: string) => {
    setEmbeddingId(docId);
    try {
      const updated = await embedDocument(docId);
      setDocuments((prev) => prev.map((d) => (d.id === docId ? updated : d)));
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    } finally {
      setEmbeddingId(null);
    }
  };

  const sourceMap = new Map(sources.map((s) => [s.id, s]));

  return (
    <ProtectedRoute>
      <AppLayout title="Knowledge Base">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Knowledge Base</h2>
            <p className="text-sm text-slate-500">{sources.length} sources · {documents.length} documents</p>
          </div>
          {canManage && (
            <Button onClick={() => setShowCreateDoc(true)}>+ Add Document</Button>
          )}
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {/* Tabs */}
        <div className="flex gap-1 bg-white border border-slate-200 rounded-lg p-1 w-fit mb-5">
          {(['documents', 'search'] as const).map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${activeTab === tab ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-slate-800'}`}>
              {tab === 'documents' ? 'Documents' : '🔍 Knowledge Search'}
            </button>
          ))}
        </div>

        {activeTab === 'documents' && (
          <>
            {/* Create Document Modal */}
            {showCreateDoc && (
              <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
                <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
                  <h2 className="text-base font-semibold text-slate-800 mb-4">Add Document</h2>
                  <form onSubmit={handleCreateDoc} className="space-y-3">
                    <select value={docSourceId} onChange={e => setDocSourceId(e.target.value)} required
                      className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                      <option value="">Select a knowledge source</option>
                      {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                    <input required placeholder="Title" value={docTitle} onChange={e => setDocTitle(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
                    <textarea required placeholder="Document content…" rows={6} value={docContent} onChange={e => setDocContent(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none" />
                    <div className="flex justify-end gap-2">
                      <Button variant="secondary" size="sm" type="button" onClick={() => setShowCreateDoc(false)}>Cancel</Button>
                      <Button size="sm" type="submit" loading={creating}>Add Document</Button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* Sources summary */}
            {!loading && sources.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {sources.map((src) => (
                  <div key={src.id} className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-full px-3 py-1 text-xs text-slate-600">
                    <span className="font-medium">{src.name}</span>
                    <Badge color={src.status === 'active' ? 'green' : 'slate'}>{src.status}</Badge>
                    <span className="text-slate-400">{src.source_type}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Documents table */}
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50">
                      <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Title</th>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Source</th>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Chunks</th>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Created</th>
                      {canManage && <th className="px-5 py-3" />}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {loading ? (
                      [1, 2, 3].map((i) => (
                        <tr key={i}><td colSpan={6}>
                          <div className="animate-pulse flex gap-4 px-4 py-3">
                            {[1,2,3,4,5].map(j => <div key={j} className="h-4 bg-slate-200 rounded flex-1" />)}
                          </div>
                        </td></tr>
                      ))
                    ) : documents.length === 0 ? (
                      <tr><td colSpan={6}>
                        <EmptyState
                          title="No documents yet"
                          description="Add a document to your knowledge base to get started."
                          action={canManage ? <Button onClick={() => setShowCreateDoc(true)}>+ Add Document</Button> : undefined}
                        />
                      </td></tr>
                    ) : (
                      documents.map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-50 transition-colors">
                          <td className="px-5 py-3.5 font-medium text-slate-800 max-w-xs truncate">{doc.title}</td>
                          <td className="px-5 py-3.5 text-slate-500 text-xs">{sourceMap.get(doc.knowledge_source_id)?.name ?? '—'}</td>
                          <td className="px-5 py-3.5"><DocumentStatusBadge status={doc.status} /></td>
                          <td className="px-5 py-3.5 text-slate-600">{doc.chunk_count}</td>
                          <td className="px-5 py-3.5 text-slate-400 text-xs">{new Date(doc.created_at).toLocaleDateString()}</td>
                          {canManage && (
                            <td className="px-5 py-3.5">
                              {doc.status !== 'embedded' && (
                                <Button
                                  variant="ghost" size="sm"
                                  loading={embeddingId === doc.id}
                                  onClick={() => handleEmbed(doc.id)}
                                >
                                  Embed
                                </Button>
                              )}
                              {doc.status === 'embedded' && (
                                <Badge color="green">Embedded</Badge>
                              )}
                            </td>
                          )}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}

        {activeTab === 'search' && (
          <Card className="p-6">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">Semantic Knowledge Search</h3>
            <form onSubmit={handleSearch} className="flex gap-2 mb-6">
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. return policy for damaged products…"
                className="flex-1 border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              <Button type="submit" loading={searching}>Search</Button>
            </form>

            {searchError && <ErrorBanner message={searchError} />}

            {searchResults.length === 0 && !searching && query && (
              <EmptyState title="No results found" description="Try a different query." />
            )}

            {searchResults.length > 0 && (
              <div className="space-y-4">
                <p className="text-xs text-slate-500">{searchResults.length} results for "<strong>{query}</strong>"</p>
                {searchResults.map((result, idx) => (
                  <div key={result.chunk_id} className="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-slate-600">Result #{idx + 1} · Chunk {result.chunk_index}</span>
                      <div className="flex items-center gap-2">
                        <Badge color={result.similarity_score > 0.7 ? 'green' : result.similarity_score > 0.4 ? 'yellow' : 'slate'}>
                          {(result.similarity_score * 100).toFixed(1)}% match
                        </Badge>
                      </div>
                    </div>
                    <p className="text-sm text-slate-700 leading-relaxed">{result.content}</p>
                  </div>
                ))}
              </div>
            )}

            {searchResults.length === 0 && !query && (
              <div className="text-center py-10">
                <p className="text-slate-400 text-sm">Enter a query to search your knowledge base semantically.</p>
                <p className="text-slate-300 text-xs mt-1">Results are powered by vector embeddings.</p>
              </div>
            )}
          </Card>
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}
