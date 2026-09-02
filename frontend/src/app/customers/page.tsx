'use client';

import { useEffect, useState, FormEvent } from 'react';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import {
  Button, Card, SkeletonRow, EmptyState, ErrorBanner, Badge, Modal,
} from '@/components/ui';
import { listCustomers, createCustomer } from '@/api/customers';
import type { Customer } from '@/types';
import { AxiosError } from 'axios';
import { useAuth } from '@/context/AuthContext';

// Quick Modal (inline, simple)
function CreateCustomerModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (c: Customer) => void;
}) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [company, setCompany] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr('');
    try {
      const cust = await createCustomer({ full_name: name, email, phone: phone || undefined, company_name: company || undefined });
      onCreated(cust);
    } catch (e) {
      if (e instanceof AxiosError) setErr(e.response?.data?.detail ?? e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-base font-semibold text-slate-800 mb-4">New Customer</h2>
        {err && <div className="mb-3"><ErrorBanner message={err} /></div>}
        <form onSubmit={handleSubmit} className="space-y-3">
          <input required placeholder="Full name" value={name} onChange={e => setName(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <input required type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <input placeholder="Phone (optional)" value={phone} onChange={e => setPhone(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <input placeholder="Company (optional)" value={company} onChange={e => setCompany(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" size="sm" type="button" onClick={onClose}>Cancel</Button>
            <Button size="sm" type="submit" loading={loading}>Create Customer</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function CustomersPage() {
  const { role } = useAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState('');

  useEffect(() => {
    listCustomers()
      .then(setCustomers)
      .catch((e) => {
        if (e instanceof AxiosError) setError(e.response?.data?.detail ?? e.message);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = customers.filter(
    (c) =>
      c.full_name.toLowerCase().includes(search.toLowerCase()) ||
      c.email.toLowerCase().includes(search.toLowerCase()) ||
      (c.company_name ?? '').toLowerCase().includes(search.toLowerCase())
  );

  const canCreate = role === 'OWNER' || role === 'ADMIN' || role === 'AGENT';

  return (
    <ProtectedRoute>
      <AppLayout title="Customers">
        {showCreate && (
          <CreateCustomerModal
            onClose={() => setShowCreate(false)}
            onCreated={(c) => {
              setCustomers((prev) => [c, ...prev]);
              setShowCreate(false);
            }}
          />
        )}

        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Customers</h2>
            <p className="text-sm text-slate-500">{customers.length} total</p>
          </div>
          {canCreate && (
            <Button onClick={() => setShowCreate(true)}>+ New Customer</Button>
          )}
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {/* Search */}
        <div className="mb-4">
          <input
            type="search"
            placeholder="Search by name, email, or company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full max-w-sm border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>

        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Name</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Email</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Company</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Created</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => <tr key={i}><td colSpan={6}><SkeletonRow cols={5} /></td></tr>)
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <EmptyState
                        title={search ? 'No customers match your search' : 'No customers yet'}
                        description="Create a customer to get started."
                        action={canCreate && !search ? <Button onClick={() => setShowCreate(true)}>+ New Customer</Button> : undefined}
                      />
                    </td>
                  </tr>
                ) : (
                  filtered.map((cust) => (
                    <tr key={cust.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-5 py-3.5 font-medium text-slate-800">{cust.full_name}</td>
                      <td className="px-5 py-3.5 text-slate-500">{cust.email}</td>
                      <td className="px-5 py-3.5 text-slate-500">{cust.company_name ?? '—'}</td>
                      <td className="px-5 py-3.5">
                        <Badge color={cust.status === 'active' ? 'green' : cust.status === 'blocked' ? 'red' : 'slate'}>
                          {cust.status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 text-slate-400 text-xs">{new Date(cust.created_at).toLocaleDateString()}</td>
                      <td className="px-5 py-3.5">
                        <Link href={`/customers/${cust.id}`}>
                          <Button variant="ghost" size="sm">View</Button>
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </AppLayout>
    </ProtectedRoute>
  );
}
